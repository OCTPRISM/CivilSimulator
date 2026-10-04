"""OpenAI-compatible client (works with OpenAI, Azure-OpenAI, vLLM, Ollama-OpenAI)."""
from __future__ import annotations

from typing import Iterable

import httpx

from ..config import get_settings
from .base import LLM, LLMResponse, Message


class OpenAILLM(LLM):
    name = "openai"

    def __init__(self) -> None:
        s = get_settings()
        if not s.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY missing")
        self._key = s.openai_api_key
        self._base = s.openai_base_url.rstrip("/")
        self._model = s.openai_model

    async def chat(
        self,
        messages: Iterable[Message],
        *,
        temperature: float = 0.8,
        max_tokens: int = 512,
        **_kwargs,
    ) -> LLMResponse:
        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {"Authorization": f"Bearer {self._key}"}
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(f"{self._base}/chat/completions",
                                  json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
        return LLMResponse(
            content=data["choices"][0]["message"]["content"],
            model=data.get("model", self._model),
            raw=data,
        )
