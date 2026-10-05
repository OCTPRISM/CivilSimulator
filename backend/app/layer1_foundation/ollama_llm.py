"""Ollama native client — supports text, multimodal (images), and embeddings.

Uses Ollama's native /api/chat & /api/embeddings rather than the OpenAI-compat
shim, so we get first-class access to multimodal `images` payloads.
"""
from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any, Iterable, Sequence

import httpx

from ..config import get_settings
from .base import LLM, LLMResponse, Message

log = logging.getLogger(__name__)


def _img_to_b64(src: str | bytes) -> str:
    if isinstance(src, bytes):
        return base64.b64encode(src).decode("ascii")
    p = Path(src)
    if p.exists():
        return base64.b64encode(p.read_bytes()).decode("ascii")
    # already base64
    return src


def _installed_model_names(base: str) -> set[str]:
    try:
        with httpx.Client(timeout=5.0) as client:
            r = client.get(f"{base}/api/tags")
            r.raise_for_status()
            models = r.json().get("models") or []
    except Exception as exc:
        log.warning("Could not list Ollama models at %s: %s", base, exc)
        return set()
    return {str(m.get("name") or "").strip() for m in models if m.get("name")}


def _pick_installed(preferred: Sequence[str], installed: set[str]) -> str | None:
    for cand in preferred:
        cand = cand.strip()
        if not cand:
            continue
        if cand in installed:
            return cand
        # Config may say "qwen3.8" while Ollama lists "qwen3.8:27b"
        prefix = cand.split(":", 1)[0]
        matches = sorted(
            name for name in installed
            if name == prefix or name.startswith(prefix + ":")
        )
        if matches:
            return matches[0]
    return None


def resolve_ollama_text_model(
    base: str,
    configured: str,
    fallbacks: str = "",
) -> str:
    """Prefer configured model; otherwise first installed fallback (gpt-oss, …)."""
    preferred = [configured, *[p.strip() for p in fallbacks.split(",") if p.strip()]]
    installed = _installed_model_names(base)
    if not installed:
        return configured
    picked = _pick_installed(preferred, installed)
    if picked is None:
        log.warning(
            "Configured Ollama text model %r not installed; using as-is. Available: %s",
            configured,
            ", ".join(sorted(n for n in installed if ":" in n)) or "(none)",
        )
        return configured
    if picked != configured:
        log.info("Ollama text model %r unavailable; using %r", configured, picked)
    return picked


class OllamaLLM(LLM):
    name = "ollama"

    def __init__(self, *, model: str | None = None) -> None:
        s = get_settings()
        self._base = s.ollama_base_url.rstrip("/")
        self._model = model or resolve_ollama_text_model(
            self._base,
            s.ollama_text_model,
            s.ollama_text_fallbacks,
        )
        self._vision_model = s.ollama_vision_model
        self._embed_model = s.ollama_embed_model

    @property
    def model(self) -> str:
        return self._model

    async def chat(
        self,
        messages: Iterable[Message],
        *,
        temperature: float = 0.8,
        max_tokens: int = 512,
        **kwargs: Any,
    ) -> LLMResponse:
        images: Sequence[str | bytes] | None = kwargs.get("images")
        force_vision = bool(kwargs.get("force_vision", False))
        json_mode = bool(kwargs.get("json_mode", False))
        msgs: list[dict[str, Any]] = [{"role": m.role, "content": m.content} for m in messages]
        # Attach images to the last user message for multimodal calls.
        if images:
            b64s = [_img_to_b64(i) for i in images]
            for m in reversed(msgs):
                if m["role"] == "user":
                    m["images"] = b64s
                    break
        model = self._vision_model if (images or force_vision) else self._model
        payload: dict[str, Any] = {
            "model": model,
            "messages": msgs,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        # qwen3.* thinking models otherwise spend minutes on chain-of-thought
        # before answering — create-session + first page would time out (500).
        if "qwen3" in model.lower():
            payload["think"] = False
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
