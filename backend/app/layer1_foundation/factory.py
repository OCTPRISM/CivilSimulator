from functools import lru_cache

from ..config import get_settings
from .base import LLM
from .llm_quota import wrap_llm_quota
from .mock_llm import MockLLM


def _build_llm() -> LLM:
    s = get_settings()
    if s.llm_provider == "ollama":
        # Do not silently replace Ollama with MockLLM: that would make a world
        # appear to evolve through model inference when it is actually scripted.
        from .ollama_llm import OllamaLLM
        return OllamaLLM()
    try:
        if s.llm_provider == "openai":
            from .openai_llm import OpenAILLM
            return OpenAILLM()
    except Exception:
        return MockLLM()
    return MockLLM()


@lru_cache
def get_llm() -> LLM:
    return wrap_llm_quota(_build_llm())
