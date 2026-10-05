"""Embedding abstraction (used by vector memory)."""
from __future__ import annotations

import hashlib
from typing import Protocol

from ..config import get_settings


class Embedder(Protocol):
    dim: int
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashEmbedder:
    """Deterministic, dependency-free fallback. NOT semantic — only for offline dev."""
    dim = 256

    async def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            v = [0.0] * self.dim
            for tok in t.split():
                h = int(hashlib.sha1(tok.encode()).hexdigest(), 16)
                for i in range(8):
                    idx = (h >> (i * 4)) & (self.dim - 1)
                    v[idx] += 1.0
            n = sum(x * x for x in v) ** 0.5 or 1.0
            out.append([x / n for x in v])
        return out


class OllamaEmbedder:
    def __init__(self, dim: int = 768) -> None:
        from .ollama_llm import OllamaLLM
        self._llm = OllamaLLM()
        self.dim = dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return await self._llm.embed(texts)


def get_embedder() -> Embedder:
    s = get_settings()
    if s.llm_provider != "ollama":
        return HashEmbedder()
    # Soft-fallback when the embed model is not pulled yet (common on fresh hosts).
    from .ollama_llm import _installed_model_names, _pick_installed
    installed = _installed_model_names(s.ollama_base_url.rstrip("/"))
    if installed and _pick_installed([s.ollama_embed_model], installed) is None:
        return HashEmbedder()
    return OllamaEmbedder()