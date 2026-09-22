from __future__ import annotations

import asyncio
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from pii_guard.core.demasking import unmask
from pii_guard.core.models import MappingRecord
from pii_guard.core.policy import Profile
from pii_guard.observability.logging import get_logger
from pii_guard.observability.metrics import observe_entities, observe_stage, observe_tokens
from pii_guard.security.auth import current_system

router = APIRouter()

logger = get_logger("pii_guard.mask")


class MaskRequest(BaseModel):
    text: str


class Entity(BaseModel):
    type: str
    start: int
    end: int


class MaskResponse(BaseModel):
    session_id: str
    masked_text: str
    entities: list[Entity]


class UnmaskRequest(BaseModel):
    session_id: str
    text: str


class UnmaskResponse(BaseModel):
    text: str


@router.post("/api/v1/mask", response_model=MaskResponse)
async def mask(
    req: MaskRequest,
    request: Request,
    system: tuple[str, Profile] = Depends(current_system),
) -> MaskResponse:
    name, profile = system
    settings = request.app.state.settings
    gate = request.app.state.concurrency_gate
    if not gate.try_enter():
        raise HTTPException(
            status_code=429,
            detail={"error": "overloaded"},
            headers={"Retry-After": str(settings.retry_after_seconds)},
        )
    try:
        config_store = request.app.state.config_store
        config_store.maybe_reload()
        _, engine = config_store.current()
        store = request.app.state.store
        cipher = request.app.state.cipher

        start = time.perf_counter()
        result = await asyncio.to_thread(engine.mask, req.text, profile)
        duration_ms = (time.perf_counter() - start) * 1000
        observe_stage("detect_mask", duration_ms / 1000)
        observe_tokens("/api/v1/mask", req.text)

        session_id = uuid.uuid4().hex
        record = MappingRecord(
            original_fp=cipher.fingerprint(req.text),
            masked_text=result.text,
            replacements=result.replacements,
        )
        start = time.perf_counter()
        await store.put_if_absent(
            f"api:{name}:{session_id}",
            record,
            request.app.state.settings.mapping_ttl_seconds,
        )
        observe_stage("store_put", time.perf_counter() - start)
        observe_entities(name, result.type_counts().items())

        entities = [
            Entity(type=r.pii_type, start=r.masked_start, end=r.masked_start + len(r.masked))
            for r in result.replacements
        ]
        logger.info(
            "mask",
            system=name,
            pii=result.type_counts(),
            duration_ms=round(duration_ms, 3),
        )
        return MaskResponse(session_id=session_id, masked_text=result.text, entities=entities)
    finally:
        gate.exit()


@router.post("/api/v1/unmask", response_model=UnmaskResponse)
async def unmask_endpoint(
    req: UnmaskRequest,
    request: Request,
    system: tuple[str, Profile] = Depends(current_system),
) -> UnmaskResponse:
    name, profile = system
    if not profile.unmask:
        raise HTTPException(status_code=403, detail={"error": "unmask_disabled"})
    settings = request.app.state.settings
    gate = request.app.state.concurrency_gate
    if not gate.try_enter():
        raise HTTPException(
            status_code=429,
            detail={"error": "overloaded"},
            headers={"Retry-After": str(settings.retry_after_seconds)},
        )
    try:
        config_store = request.app.state.config_store
        config_store.maybe_reload()
        store = request.app.state.store

        start = time.perf_counter()
        record = await store.get(f"api:{name}:{req.session_id}")
        observe_stage("store_get", time.perf_counter() - start)
        if record is None:
            raise HTTPException(status_code=404, detail={"error": "session_not_found"})

        start = time.perf_counter()
        result = await asyncio.to_thread(unmask, req.text, record)
        observe_stage("unmask", time.perf_counter() - start)
        logger.info("unmask", system=name)
        return UnmaskResponse(text=result)
    finally:
        gate.exit()
