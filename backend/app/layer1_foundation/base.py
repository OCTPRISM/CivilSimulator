from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterable, Literal

Role = Literal["system", "user", "assistant"]


@dataclass
class Message:
    role: Role
    content: str


@dataclass
class LLMResponse:
    content: str
    model: str
    raw: dict | None = None


class LLM(ABC):
    """Minimal LLM interface used by the whole stack."""

    name: str = "abstract"

    @abstractmethod
    async def chat(
        self,
        messages: Iterable[Message],
        *,
        temperature: float = 0.8,
        max_tokens: int = 512,
        **kwargs,
    ) -> LLMResponse: ...

    async def complete(self, prompt: str, *, system: str | None = None, **kw) -> str:
        msgs: list[Message] = []
        if system:
            msgs.append(Message("system", system))
        msgs.append(Message("user", prompt))
        resp = await self.chat(msgs, **kw)
        return resp.content
