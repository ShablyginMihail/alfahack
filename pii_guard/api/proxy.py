from __future__ import annotations

import asyncio
import dataclasses
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from pii_guard.core.demasking import masked_regions, replace_masked_fragments
from pii_guard.core.models import Replacement
from pii_guard.core.policy import Profile
from pii_guard.llm.client import LLMError, MockLLM
from pii_guard.observability.logging import get_logger
from pii_guard.observability.metrics import observe_entities, observe_stage, observe_tokens
from pii_guard.security.auth import current_system

router = APIRouter()

logger = get_logger("pii_guard.chat")

SEP = "\n␞\n"
_SEP_CHAR = "␞"


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)
    model: str | None = None
    stream: bool = False


def _type_counts(replacements: list[Replacement]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for replacement in replacements:
        counts[replacement.pii_type] = counts.get(replacement.pii_type, 0) + 1
    return counts


@router.post("/v1/chat/completions")
async def chat_completions(
    req: ChatRequest,
    request: Request,
    system: tuple[str, Profile] = Depends(current_system),
) -> dict[str, Any]:
    name, profile = system
    settings = request.app.state.settings
    gate = request.app.state.concurrency_gate
    weight = sum(len(m.content) for m in req.messages)
    if not gate.try_enter(weight):
        raise HTTPException(
            status_code=429,
            detail={"error": "overloaded"},
            headers={"Retry-After": str(settings.retry_after_seconds)},
        )
    try:
        if req.stream:
            raise HTTPException(status_code=400, detail={"error": "streaming_not_supported"})

        config_store = request.app.state.config_store
        config_store.maybe_reload()
        _, engine = config_store.current()
        llm_client = request.app.state.llm_client

        start = time.perf_counter()
        contents = [m.content for m in req.messages]
        joined = SEP.join(contents)
        if any(_SEP_CHAR in content for content in contents):
            masked_messages: list[dict[str, str]] = []
            replacements: list[Replacement] = []
            for message in req.messages:
                result = await asyncio.to_thread(engine.mask, message.content, profile)
                masked_messages.append({"role": message.role, "content": result.text})
                replacements.extend(result.replacements)
        else:
            result = await asyncio.to_thread(engine.mask, joined, profile)
            masked_contents = result.text.split(SEP)
            masked_messages = [
                {"role": message.role, "content": content}
                for message, content in zip(req.messages, masked_contents, strict=True)
            ]
            replacements = list(result.replacements)
        duration_ms = (time.perf_counter() - start) * 1000
        observe_stage("detect_mask", duration_ms / 1000)
        observe_tokens("/v1/chat/completions", joined)

        masked_joined = SEP.join(message["content"] for message in masked_messages)
        strict_profile = dataclasses.replace(profile, strict=True)
        recheck_spans = await asyncio.to_thread(engine.analyze, masked_joined, strict_profile)
        if profile.mask_style == "synthetic":
            regions = masked_regions(masked_joined, replacements)
            recheck_spans = [
                span
                for span in recheck_spans
                if not any(span.start < end and start < span.end for start, end in regions)
            ]
        recheck_masked = len(recheck_spans)
        if recheck_spans:
            recheck_result = await asyncio.to_thread(
                engine.mask_spans, masked_joined, recheck_spans, strict_profile
            )
            rechecked_contents = recheck_result.text.split(SEP)
            masked_messages = [
                {"role": message["role"], "content": content}
                for message, content in zip(masked_messages, rechecked_contents, strict=True)
            ]
            replacements.extend(recheck_result.replacements)

        llm_name = llm_client.name
        start = time.perf_counter()
        try:
            answer = await llm_client.complete(masked_messages)
        except LLMError:
            logger.warning("llm_fallback", system=name)
            answer = await MockLLM().complete(masked_messages)
            llm_name = "mock_fallback"
        observe_stage("llm", time.perf_counter() - start)

        llm_answer_masked = answer
        if profile.unmask:
            answer = await asyncio.to_thread(replace_masked_fragments, answer, replacements)

        entities = _type_counts(replacements)
        observe_entities(name, entities.items())

        logger.info(
            "chat",
            system=name,
            entities=entities,
            llm=llm_name,
            recheck_masked=recheck_masked,
            duration_ms=round(duration_ms, 3),
        )

        return {
            "id": "chatcmpl-" + uuid.uuid4().hex,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": req.model or settings.llm_model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": answer},
                    "finish_reason": "stop",
                }
            ],
            "pii_guard": {
                "system": name,
                "llm": llm_name,
                "masked_messages": masked_messages,
                "llm_answer_masked": llm_answer_masked,
                "entities": entities,
                "recheck_masked": recheck_masked,
            },
        }
    finally:
        gate.exit(weight)
