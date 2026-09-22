from __future__ import annotations

from typing import Protocol

import httpx

from pii_guard.settings import Settings


class LLMError(Exception):
    """Ошибка обращения к LLM-провайдеру."""


class LLMClient(Protocol):
    name: str

    async def complete(self, messages: list[dict[str, str]]) -> str: ...

    async def aclose(self) -> None: ...


class MockLLM:
    name = "mock"

    async def complete(self, messages: list[dict[str, str]]) -> str:
        user = [m for m in messages if m.get("role") == "user"]
        if not user:
            return "Запрос получен."
        content = user[-1].get("content", "")
        return (
            f"Запрос получен. Вы написали: «{content}». "
            "Персональные данные в запросе заменены, поэтому модель видит только маски."
        )

    async def aclose(self) -> None:
        return None


class OpenAICompatibleLLM:
    name = "openai-compatible"

    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        model: str,
        timeout_seconds: float,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._client = httpx.AsyncClient(timeout=timeout_seconds)

    async def complete(self, messages: list[dict[str, str]]) -> str:
        headers = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        try:
            response = await self._client.post(
                f"{self._base_url}/chat/completions",
                json={"model": self._model, "messages": messages, "stream": False},
                headers=headers,
            )
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM request failed: {type(exc).__name__}") from exc
        if response.status_code < 200 or response.status_code >= 300:
            raise LLMError(f"LLM returned status {response.status_code}")
        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMError("LLM returned an invalid response") from exc
        if not isinstance(content, str):
            raise LLMError("LLM returned an invalid response")
        return content

    async def aclose(self) -> None:
        await self._client.aclose()


def create_llm_client(settings: Settings) -> LLMClient:
    if settings.llm_base_url:
        return OpenAICompatibleLLM(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key.get_secret_value() if settings.llm_api_key else None,
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    return MockLLM()
