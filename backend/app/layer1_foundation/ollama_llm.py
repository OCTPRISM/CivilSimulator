"""Ollama native client — supports text, multimodal (images), and embeddings.

Uses Ollama's native /api/chat & /api/embeddings rather than the OpenAI-compat
shim, so we get first-class access to multimodal `images` payloads.
"""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Iterable, Sequence

import httpx

from ..config import get_settings
from .base import LLM, LLMResponse, Message


def _img_to_b64(src: str | bytes) -> str:
    if isinstance(src, bytes):
        return base64.b64encode(src).decode("ascii")
    p = Path(src)
    if p.exists():
        return base64.b64encode(p.read_bytes()).decode("ascii")
    # already base64
    return src


class OllamaLLM(LLM):
    name = "ollama"

    def __init__(self, *, model: str | None = None) -> None:
        s = get_settings()
        self._base = s.ollama_base_url.rstrip("/")
        self._model = model or s.ollama_text_model
        self._vision_model = s.ollama_vision_model
        self._embed_model = s.ollama_embed_model

    async def chat(
        self,
        messages: Iterable[Message],
        *,
        temperature: float = 0.8,
        max_tokens: int = 512,
        images: Sequence[str | bytes] | None = None,
        force_vision: bool = False,
        json_mode: bool = False,
    ) -> LLMResponse:
        msgs = [{"role": m.role, "content": m.content} for m in messages]
        # Attach images to the last user message for multimodal calls.
        if images:
            b64s = [_img_to_b64(i) for i in images]
            for m in reversed(msgs):
                if m["role"] == "user":
                    m["images"] = b64s
                    break
        model = self._vision_model if (images or force_vision) else self._model
        payload = {
            "model": model,
            "messages": msgs,
            "stream": False,
            # qwen3.* thinking models otherwise spend minutes on chain-of-thought
            # before answering — create-session + first page would time out (500).
            "think": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if json_mode:
            payload["format"] = "json"
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(f"{self._base}/api/chat", json=payload)
            r.raise_for_status()
            data = r.json()
        return LLMResponse(
            content=(data.get("message") or {}).get("content", ""),
            model=data.get("model", model),
            raw=data,
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        async with httpx.AsyncClient(timeout=120) as client:
            for t in texts:
                r = await client.post(
                    f"{self._base}/api/embeddings",
                    json={"model": self._embed_model, "prompt": t},
                )
                r.raise_for_status()
                out.append(r.json()["embedding"])
        return out
