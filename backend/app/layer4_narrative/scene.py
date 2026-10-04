from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class Beat:
    """One atomic line of the page: either narration, an agent line, or a system note."""
    kind: Literal["narration", "speech", "action", "system"]
    speaker: str | None        # None for narration / system
    content: str


@dataclass
class Scene:
    location_id: str
    location_name: str
    summary: str               # one-line "where & when"
    present_agent_ids: list[str] = field(default_factory=list)


@dataclass
class Page:
    """The unit Layer 5 renders as one flipped page."""
    page_no: int
    chapter: str
    scene: Scene
    beats: list[Beat]
    choices: list = field(default_factory=list)   # list[dict] {label, hint, action}
    tension: float = 0.0                                # 0..1 dramatic tension
