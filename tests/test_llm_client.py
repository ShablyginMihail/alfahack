from __future__ import annotations

import secrets

import httpx
import pytest
import respx
from pydantic import SecretStr

from pii_guard.llm.client import (
    LLMError,
    MockLLM,
    OpenAICompatibleLLM,
    create_llm_client,
)
from pii_guard.settings import Settings

API_KEY = secrets.token_urlsafe(16)
LLM_BASE_URL = "https://llm.example"
LLM_CHAT_URL = "https://llm.example/chat/completions"


@pytest.mark.asyncio
async def test_mock_llm_uses_last_user_message() -> None:
    llm = MockLLM()
    messages = [
        {"role": "system", "content": "ignored"},
        {"role": "user", "content": "привет"},
        {"role": "assistant", "content": "промежуточный"},
        {"role": "user", "content": "как дела"},
    ]
    result = await llm.complete(messages)
    assert "как дела" in result
    assert "привет" not in result
    assert "маски" in result


@pytest.mark.asyncio
async def test_mock_llm_no_user_message() -> None:
    llm = MockLLM()
    result = await llm.complete([{"role": "system", "content": "x"}])
    assert result == "Запрос получен."


@pytest.mark.asyncio
async def test_mock_llm_aclose_noop() -> None:
    llm = MockLLM()
    await llm.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_openai_compatible_success() -> None:
    route = respx.post(LLM_CHAT_URL).mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})
    )
    llm = OpenAICompatibleLLM(
        base_url="https://llm.example/",
        api_key=API_KEY,
        model="gpt-test",
        timeout_seconds=5.0,
    )
    try:
        result = await llm.complete([{"role": "user", "content": "hi"}])
    finally:
        await llm.aclose()
    assert result == "ok"
    assert route.called
    request = route.calls[0].request
    assert request.headers["Authorization"] == f"Bearer {API_KEY}"
    assert request.url.path == "/chat/completions"


@pytest.mark.asyncio
@respx.mock
async def test_openai_compatible_status_500() -> None:
    respx.post(LLM_CHAT_URL).mock(return_value=httpx.Response(500, text="boom"))
    llm = OpenAICompatibleLLM(
        base_url=LLM_BASE_URL,
        api_key=None,
        model="m",
        timeout_seconds=5.0,
    )
    try:
        with pytest.raises(LLMError):
            await llm.complete([{"role": "user", "content": "hi"}])
    finally:
        await llm.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_openai_compatible_missing_choices() -> None:
    respx.post(LLM_CHAT_URL).mock(return_value=httpx.Response(200, json={"foo": "bar"}))
    llm = OpenAICompatibleLLM(
        base_url=LLM_BASE_URL,
        api_key=None,
        model="m",
        timeout_seconds=5.0,
    )
    try:
        with pytest.raises(LLMError):
            await llm.complete([{"role": "user", "content": "hi"}])
    finally:
        await llm.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_openai_compatible_connect_error() -> None:
    respx.post(LLM_CHAT_URL).mock(side_effect=httpx.ConnectError("connection refused"))
    llm = OpenAICompatibleLLM(
        base_url=LLM_BASE_URL,
        api_key=None,
        model="m",
        timeout_seconds=5.0,
    )
    try:
        with pytest.raises(LLMError):
            await llm.complete([{"role": "user", "content": "hi"}])
    finally:
        await llm.aclose()


def test_create_llm_client_mock() -> None:
    client = create_llm_client(Settings(llm_base_url=None))
    assert isinstance(client, MockLLM)


def test_create_llm_client_openai() -> None:
    client = create_llm_client(
        Settings(llm_base_url=LLM_BASE_URL, llm_api_key=SecretStr("k"), llm_model="m")
    )
    assert isinstance(client, OpenAICompatibleLLM)
