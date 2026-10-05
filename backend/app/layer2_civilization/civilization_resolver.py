"""Resolve built-in seeds and user custom civilizations."""
from __future__ import annotations

from typing import Any

from ..layer6_persistence.custom_civilizations import get_custom_by_key, list_custom_civilizations
from .player_catalog import get_player_catalog
from .seed import CivilizationSeed, list_seeds, load_seed


def list_all_seeds(user_id: str | None = None) -> list[dict[str, Any]]:
    out = [dict(s) for s in list_seeds()]
    if user_id:
        for c in list_custom_civilizations(user_id):
            out.append(c)
    return out


def load_seed_any(key: str, user_id: str | None = None) -> CivilizationSeed:
    if key.startswith("custom_"):
        custom = get_custom_by_key(key, user_id=user_id)
        if not custom:
            raise FileNotFoundError(f"custom civilization '{key}' not found")
        return custom_to_seed(custom)
    return load_seed(key)


def custom_to_seed(custom: dict[str, Any]) -> CivilizationSeed:
    cfg = custom["config"]
    key = custom["key"]
    name = cfg["name"]
    genre = (cfg.get("genre") or "custom").strip() or "custom"
    events = cfg.get("historical_events") or []
    professions = cfg.get("professions") or []

    rules = [str(r).strip() for r in (cfg.get("rules") or []) if str(r).strip()]
    if not rules:
        rules = [
            cfg["operating_logic"],
            f"政权组织：{cfg.get('government_form', '未指定')}",
            f"当前阶段：{cfg.get('current_stage', '起始')}",
        ]
        for ev in events[:5]:
            if isinstance(ev, dict):
                rules.append(f"史事·{ev.get('title', '')}：{str(ev.get('description', ''))[:80]}")

    premise = (cfg.get("premise") or "").strip() or (
        f"{cfg.get('current_stage', '起始阶段')}。"
        f"{cfg['operating_logic'][:200]}"
    )

    locations = list(cfg.get("locations") or [])
    if not locations:
        locations = [
            {
                "name": f"{name}·中枢",
                "description": f"政权形式为{cfg.get('government_form', '未指定')}的权力与决策中心。",
                "tags": ["中枢", "政务"],
            },
            {
                "name": f"{name}·市井",
                "description": "各阶层交错往来的日常空间，谣言与生计同样在此流转。",
                "tags": ["市井", "舆情"],
            },
            {
                "name": f"{name}·边域",
                "description": "冲突、迁徙与不确定性的前沿。",
                "tags": ["边域", "军事"],
            },
        ]

    factions = list(cfg.get("factions") or [])
    if not factions:
        for cls, ratio in (cfg.get("class_structure") or {}).items():
            if ratio >= 0.08:
                factions.append({
                    "name": _class_label(cls),
                    "ideology": f"代表{_class_label(cls)}利益，人口占比约 {ratio * 100:.0f}%",
                })
    if not factions:
        factions = [{"name": "主流社会", "ideology": "维持秩序与生计"}]

    npc_archetypes = []
    for i, prof in enumerate(professions[:6]):
        if isinstance(prof, dict) and prof.get("name"):
            npc_archetypes.append({
                "name": prof["name"][:20] if i == 0 else f"{prof['name'][:16]}{i + 1}",
                "home": locations[i % len(locations)]["name"],
                "avatar": "👤",
                "profession": prof["name"][:24],
                "persona": (prof.get("description") or f"{prof['name']}，在此文明中扮演关键角色。")[:200],
                "goals": ["在此阶段立足并影响局势"],
                "traits": ["谨慎", "务实"],
                "schedule": [
                    {"from": 8, "to": 12, "location": locations[0]["name"], "activity": "处理公务"},
                    {"from": 14, "to": 18, "location": locations[min(1, len(locations) - 1)]["name"], "activity": "走访市井"},
                ],
                "economy": {"daily_capacity": 1.0, "daily_expenses": 10},
            })
    if not npc_archetypes:
        npc_archetypes = [{
            "name": "见证者",
            "home": locations[0]["name"],
            "avatar": "📜",
            "profession": "史官",
            "persona": "记录这个文明转折的见证者。",
            "goals": ["见证并记录当前阶段"],
            "traits": ["冷静", "观察"],
            "schedule": [
                {"from": 8, "to": 18, "location": locations[0]["name"], "activity": "记录与观察"},
            ],
            "economy": {"daily_capacity": 0.9, "daily_expenses": 8},
        }]

    opening = (cfg.get("opening_scene") or "").strip() or (
        f"你踏入{name}——{cfg.get('current_stage', '故事正在发生')}。"
    )
    return CivilizationSeed(
        key=key,
        name=name,
        genre=genre,
        premise=premise,
        rules=rules,
        locations=locations,
        factions=factions,
        npc_archetypes=npc_archetypes,
        opening_scene=opening,
    )


def custom_catalog(custom: dict[str, Any]) -> dict[str, Any]:
    cfg = custom["config"]
    key = custom["key"]
    roles = cfg.get("roles") or []
    professions = cfg.get("professions") or []
    variants = []
    for i, role in enumerate(roles):
        if not isinstance(role, dict):
            continue
        variants.append({
            "key": role.get("key") or f"role_{i}",
            "name": role.get("name") or f"角色{i + 1}",
            "avatar": role.get("avatar") or "🧑",
            "persona": role.get("persona") or role.get("description") or "在此文明中寻找自己的位置。",
            "goals": role.get("goals") or ["在此文明中立足"],
            "traits": role.get("traits") or ["谨慎"],
            "profession": role.get("profession") or role.get("name") or "居民",
            "equipment": role.get("equipment") or {},
            "starting_items": role.get("starting_items") or [{"name": "铜钱", "kind": "gold", "qty": 50}],
        })
    playable_profs = [p for p in professions if isinstance(p, dict) and p.get("playable")]
    for i, prof in enumerate(playable_profs):
        variants.append({
            "key": f"prof_{i}",
            "name": prof.get("name") or f"职业{i + 1}",
            "avatar": "⚒️",
            "persona": prof.get("description") or f"以{prof.get('name', '此职业')}身份生活。",
            "goals": ["完成本职工作并谋求发展"],
            "traits": ["勤勉"],
            "profession": prof.get("name") or "居民",
            "equipment": {},
            "starting_items": [{"name": "铜钱", "kind": "gold", "qty": 40}],
        })
    if not variants:
        variants = [{
            "key": "traveler",
            "name": "外来旅人",
            "avatar": "🧳",
            "persona": "刚踏入此文明的外来者。",
            "goals": ["了解并融入这个文明"],
            "traits": ["好奇", "谨慎"],
            "profession": "旅人",
            "equipment": {},
            "starting_items": [{"name": "铜钱", "kind": "gold", "qty": 30}],
        }]
    return {
        "seed_key": key,
        "categories": [{
            "key": "custom_roles",
            "name": "自定义角色",
            "description": "你在该文明中可扮演的身份",
            "variants": variants,
        }],
    }


def get_catalog_any(seed_key: str, user_id: str | None = None) -> dict[str, Any]:
    if seed_key.startswith("custom_"):
        custom = get_custom_by_key(seed_key, user_id=user_id)
        if not custom:
            return get_player_catalog(seed_key)
        return custom_catalog(custom)
    return get_player_catalog(seed_key)


def civilization_context(key: str, user_id: str | None = None) -> dict[str, Any]:
    """Summary context for lab simulations."""
    if key.startswith("custom_"):
        custom = get_custom_by_key(key, user_id=user_id)
        if not custom:
            raise FileNotFoundError(key)
        cfg = custom["config"]
        return {
            "key": key,
            "name": cfg["name"],
            "genre": "custom",
            "class_structure": cfg.get("class_structure") or {},
            "age_structure": cfg.get("age_structure") or {},
            "operating_logic": cfg.get("operating_logic", ""),
            "government_form": cfg.get("government_form", ""),
            "current_stage": cfg.get("current_stage", ""),
            "historical_events": cfg.get("historical_events") or [],
        }
    seed = load_seed(key)
    return {
        "key": key,
        "name": seed.name,
        "genre": seed.genre,
        "premise": seed.premise,
        "rules": seed.rules,
        "current_stage": seed.premise[:120],
        "class_structure": {"middle": 0.4, "labor": 0.5, "ruling": 0.1},
        "age_structure": {"child": 0.18, "youth": 0.22, "adult": 0.40, "middle_aged": 0.12, "elder": 0.08},
    }


def _class_label(key: str) -> str:
    return {
        "ruling": "统治阶层",
        "middle": "中产市民",
        "labor": "劳动阶层",
        "marginal": "边缘群体",
    }.get(key, key)


def resolve_variant_any(
    seed_key: str, category_key: str, variant_key: str, user_id: str | None = None,
) -> dict | None:
    catalog = get_catalog_any(seed_key, user_id)
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

