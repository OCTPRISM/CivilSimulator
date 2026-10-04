"""Civilization seeds — pre-authored world templates."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .world import Faction, Location, World, WorldClock, new_id

SEEDS_DIR = Path(__file__).resolve().parent.parent / "seeds"


@dataclass
class CivilizationSeed:
    key: str                # ancient / scifi / wuxia / xuanhuan / mystery
    name: str
    genre: str
    premise: str
    rules: list[str]
    locations: list[dict] = field(default_factory=list)
    factions: list[dict] = field(default_factory=list)
    npc_archetypes: list[dict] = field(default_factory=list)
    opening_scene: str = ""

    def materialize(self) -> World:
        w = World(
            id=new_id("world"),
            name=self.name,
            genre=self.genre,
            premise=self.premise,
            rules=list(self.rules),
            clock=WorldClock(era="起始", tick=0),
        )
        for loc in self.locations:
            w.add_location(loc["name"], loc["description"], loc.get("tags", []))
        for fac in self.factions:
            f = Faction(id=new_id("fac"), name=fac["name"], ideology=fac["ideology"])
            w.factions[f.id] = f
        return w


def list_seeds() -> list[dict]:
    out = []
    for f in sorted(SEEDS_DIR.glob("*.json")):
        if f.name.startswith("_") or f.name == "player_catalog.json":
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        if "key" not in data:
            continue
        out.append({
            "key": data["key"],
            "name": data["name"],
            "genre": data["genre"],
            "premise": data["premise"],
        })
    return out


def load_seed(key: str) -> CivilizationSeed:
    path = SEEDS_DIR / f"{key}.json"
    if not path.exists():
        raise FileNotFoundError(f"seed '{key}' not found")
    data = json.loads(path.read_text(encoding="utf-8"))
    return CivilizationSeed(**data)
