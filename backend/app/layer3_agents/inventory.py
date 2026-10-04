"""Simple inventory / equipment for agents."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4


class ItemKind(str, Enum):
    GOLD = "gold"
    FOOD = "food"
    EQUIPMENT = "equipment"
    MISC = "misc"


@dataclass
class Item:
    id: str
    name: str
    kind: ItemKind
    qty: float = 1.0
    meta: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind.value,
            "qty": self.qty,
            "meta": dict(self.meta),
        }


def new_item(name: str, kind: ItemKind, qty: float = 1.0, **meta) -> Item:
    return Item(id=f"item_{uuid4().hex[:8]}", name=name, kind=kind, qty=qty, meta=meta)


def grant_rewards(inventory: list[Item], rewards: dict) -> list[Item]:
    """Merge reward dict {gold, food:[], equipment:[]} into inventory list."""
    out = list(inventory)
    gold = float(rewards.get("gold", 0) or 0)
    if gold:
        merged = False
        for it in out:
            if it.kind == ItemKind.GOLD:
                it.qty += gold
                merged = True
                break
        if not merged:
            out.append(new_item("铜钱", ItemKind.GOLD, gold))
    for f in rewards.get("food") or []:
        if isinstance(f, str):
            out.append(new_item(f, ItemKind.FOOD))
        elif isinstance(f, dict):
            out.append(new_item(f.get("name", "食物"), ItemKind.FOOD, f.get("qty", 1)))
    for e in rewards.get("equipment") or []:
        if isinstance(e, str):
            out.append(new_item(e, ItemKind.EQUIPMENT, meta={"slot": "misc"}))
        elif isinstance(e, dict):
            out.append(new_item(
                e.get("name", "装备"), ItemKind.EQUIPMENT,
                meta={"slot": e.get("slot", "misc"), **e},
            ))
    return out


def inventory_to_dict(items: list[Item]) -> list[dict]:
    return [i.as_dict() for i in items]
