from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


def new_id(prefix: str = "id") -> str:
    return f"{prefix}_{uuid4().hex[:10]}"


@dataclass
class Location:
    id: str
    name: str
    description: str
    tags: list[str] = field(default_factory=list)


@dataclass
class Faction:
    id: str
    name: str
    ideology: str
    relations: dict[str, float] = field(default_factory=dict)  # faction_id -> [-1,1]


@dataclass
class WorldClock:
    """Abstract time. `era` is a free-form label; `tick` is monotonic.
    One tick == one in-world hour. `day` and `hour_of_day` are derived.
    """
    era: str = "起始"
    tick: int = 0
    start_hour: int = 6   # the hour of day at tick=0

    def advance(self, n: int = 1) -> None:
        self.tick += n

    @property
    def hour_of_day(self) -> int:
        return (self.start_hour + self.tick) % 24

    @property
    def day(self) -> int:
        return (self.start_hour + self.tick) // 24

    def label(self) -> str:
        h = self.hour_of_day
        if   5 <= h < 8:   period = "清晨"
        elif 8 <= h < 12:  period = "上午"
        elif 12 <= h < 14: period = "正午"
        elif 14 <= h < 18: period = "午后"
        elif 18 <= h < 21: period = "黄昏"
        elif 21 <= h < 24: period = "深夜"
        else:              period = "凌晨"
        return f"第{self.day+1}日·{period}（{h:02d}:00）"


@dataclass
class World:
    id: str
    name: str
    genre: str                      # ancient / scifi / wuxia / xuanhuan / mystery
    premise: str                    # one-paragraph backstory
    rules: list[str]                # natural-language laws of physics / magic / etc.
    clock: WorldClock = field(default_factory=WorldClock)
    locations: dict[str, Location] = field(default_factory=dict)
    factions: dict[str, Faction] = field(default_factory=dict)
    facts: list[str] = field(default_factory=list)        # canonical world facts
    agents: list[str] = field(default_factory=list)       # agent ids living here

    # ---- mutation helpers ----
    def add_location(self, name: str, description: str, tags: list[str] | None = None) -> Location:
        loc = Location(id=new_id("loc"), name=name, description=description, tags=tags or [])
        self.locations[loc.id] = loc
        return loc

    def add_faction(self, name: str, ideology: str) -> Faction:
        f = Faction(id=new_id("fac"), name=name, ideology=ideology)
        self.factions[f.id] = f
        return f

    def snapshot(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "genre": self.genre,
            "premise": self.premise,
            "rules": list(self.rules),
            "clock": {"era": self.clock.era, "tick": self.clock.tick,
                      "hour": self.clock.hour_of_day, "day": self.clock.day,
                      "label": self.clock.label()},
            "locations": [l.__dict__ for l in self.locations.values()],
            "factions": [f.__dict__ for f in self.factions.values()],
            "facts": list(self.facts),
            "agents": list(self.agents),
            "visual_capabilities": {
                "exploration_enabled": self.genre in (
                    "wuxia", "ancient", "xuanhuan", "modern", "scifi", "mystery",
                ),
                "map_fallback": True,
                "character_lod": "standard",
            },
        }
