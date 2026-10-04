"""Player character catalog — categories & swipeable variants per civilization."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from uuid import uuid4

from ..layer3_agents import Agent, AgentKind
from ..layer3_agents.inventory import ItemKind, grant_rewards, new_item
from .world import World

CATALOG_PATH = Path(__file__).resolve().parent.parent / "seeds" / "player_catalog.json"


@lru_cache
def _load_catalog() -> dict[str, Any]:
    if not CATALOG_PATH.exists():
        return {}
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def get_player_catalog(seed_key: str) -> dict[str, Any]:
    data = _load_catalog().get(seed_key)
    if not data:
        out = {"seed_key": seed_key, "categories": _fallback_categories(seed_key)}
    else:
        out = {"seed_key": seed_key, **data}
    for cat in out.get("categories", []):
        for var in cat.get("variants", []):
            var.setdefault(
                "figure",
                f"{seed_key}_{var.get('key', 'default')}".replace("-", "_"),
            )
    return out


def _fallback_categories(seed_key: str) -> list[dict]:
    return [{
        "key": "traveler",
        "name": "旅人",
        "description": "初入此界的过客",
        "variants": [{
            "key": "default",
            "name": "无名旅人",
            "avatar": "🧳",
            "persona": "一名身世成谜的旅人，对此地一无所知。",
            "goals": ["在此地活下去"],
            "traits": ["谨慎", "好奇"],
            "profession": "旅人",
            "equipment": {"行囊": "旧包袱"},
            "starting_items": [{"name": "铜钱", "kind": "gold", "qty": 20}],
        }],
    }]


def resolve_variant(seed_key: str, category_key: str, variant_key: str) -> dict | None:
    catalog = get_player_catalog(seed_key)
    for cat in catalog.get("categories", []):
        if cat.get("key") != category_key:
            continue
        for var in cat.get("variants", []):
            if var.get("key") == variant_key:
                figure = var.get("figure") or f"{seed_key}_{variant_key}".replace("-", "_")
                return {
                    **var,
                    "category_key": category_key,
                    "category_name": cat.get("name", ""),
                    "figure": figure,
                }
    return None


def spawn_player_from_variant(
    world: World, variant: dict, seed_key: str = "", skin: str | None = None,
) -> Agent:
    loc_id = next(iter(world.locations)) if world.locations else None
    equipment = dict(variant.get("equipment") or {})
    figure = variant.get("figure") or f"{seed_key}_{variant.get('key', 'default')}".replace("-", "_")
    skin_id = skin if skin in ("fair", "tan", "warm", "pale") else "fair"
    agent = Agent(
        id=f"agent_{uuid4().hex[:10]}",
        name=variant.get("name", "无名旅人"),
        kind=AgentKind.PLAYER,
        persona=variant.get("persona", ""),
        goals=list(variant.get("goals") or []),
        traits=list(variant.get("traits") or []),
        location_id=loc_id,
        avatar=variant.get("avatar", "👤"),
        profession=variant.get("profession", ""),
        equipment=equipment,
        appearance={
            "figure": figure,
            "category": variant.get("category_key", ""),
            "skin": skin_id,
        },
    )
    inv: list = []
    for spec in variant.get("starting_items") or []:
        if isinstance(spec, str):
            inv.append(new_item(spec, ItemKind.MISC))
            continue
        kind = ItemKind(spec.get("kind", "misc"))
        inv.append(new_item(
            spec.get("name", "物品"), kind,
            float(spec.get("qty", 1)),
            **{k: v for k, v in spec.items() if k not in ("name", "kind", "qty")},
        ))
    rewards = variant.get("rewards") or {}
    if rewards:
        inv = grant_rewards(inv, rewards)
    agent.inventory = inv
    if not agent.savings:
        for it in inv:
            if it.kind == ItemKind.GOLD:
                agent.savings = float(it.qty)
                break
    return agent


def npc_figure_from_archetype(arc: dict, genre: str = "ancient") -> str:
    if arc.get("figure"):
        return str(arc["figure"])
    name = arc.get("name", "")
    prof = arc.get("profession", "") or ""
    text = f"{name}{prof}"
    if "杀手" in text or "无面" in text or "鬼" in text:
        return "npc_rogue_mask"
    if "剑" in text or "庄" in text or "首座" in text:
        return "npc_swordsman"
    if "丐" in text or "醉" in text:
        return "npc_drunkard"
    if "船" in text or "艄" in text or "摆渡" in text:
        return "npc_boatman"
    if "说书" in text:
        return "npc_storyteller"
    if "医" in text or "郎中" in text:
        if genre == "mystery":
            return "mystery_doctor"
        if genre == "xuanhuan":
            return "xuanhuan_alchemist"
        return "wuxia_physician"
    pools = {
        "scifi": ["scifi_comms", "scifi_engineer", "scifi_scout", "scifi_xeno"],
        "mystery": ["mystery_detective", "mystery_reporter", "mystery_doctor"],
        "xuanhuan": ["xuanhuan_outer", "xuanhuan_rogue", "xuanhuan_alchemist"],
        "ancient": ["ancient_student", "ancient_clerk", "ancient_guard", "ancient_archer", "ancient_trader"],
        "wuxia": ["npc_default", "wuxia_wanderer", "wuxia_physician", "wuxia_beggar"],
    }
    pool = pools.get(genre, ["npc_default"])
    h = sum(ord(c) for c in text) or 0
    return pool[h % len(pool)]
