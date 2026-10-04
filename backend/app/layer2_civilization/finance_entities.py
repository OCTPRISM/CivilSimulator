"""Civilization-scoped cities and typical enterprises for finance lab."""
from __future__ import annotations

import hashlib
import re
from typing import Any

from .civilization_resolver import load_seed_any

_CITY_SPLIT = re.compile(r"[·•\-—]")


def _slug(text: str) -> str:
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()[:10]
    return h


def _city_from_location(loc: dict[str, Any]) -> dict[str, Any]:
    raw = str(loc.get("name") or "").strip()
    if not raw:
        return {}
    parts = [p.strip() for p in _CITY_SPLIT.split(raw) if p.strip()]
    name = parts[0] if parts else raw
    return {
        "key": _slug(name),
        "name": name[:24],
        "description": str(loc.get("description") or "")[:120],
        "tags": list(loc.get("tags") or []),
    }


_SECTOR_BY_GENRE: dict[str, str] = {
    "modern": "综合服务",
    "enterprise": "科技",
    "securities": "金融",
    "military": "军工",
    "wuxia": "江湖贸易",
    "ancient": "盐铁漕运",
    "scifi": "星际工业",
    "xuanhuan": "灵材",
    "mystery": "实业",
    "custom": "工商",
}


_FACTION_SECTOR_HINTS: list[tuple[str, str]] = [
    ("基金", "创投"), ("联盟", "产业"), ("帮", "组织"), ("堂", "贸易"),
    ("庄", "制造"), ("军", "军工"), ("银", "金融"), ("商", "商贸"),
    ("社区", "民生"), ("市政", "公用"), ("员工", "人力"),
]


def _infer_sector(name: str, genre: str) -> str:
    for hint, sector in _FACTION_SECTOR_HINTS:
        if hint in name:
            return sector
    return _SECTOR_BY_GENRE.get(genre, "工商")


def _base_price(seed: str, key: str, lo: float = 40.0, hi: float = 180.0) -> float:
    h = int(hashlib.sha256(f"{seed}:{key}".encode()).hexdigest()[:8], 16)
    span = hi - lo
    return round(lo + (h % 1000) / 1000.0 * span, 2)


_SEED_CITY_EXTRAS: dict[str, list[dict[str, Any]]] = {
    "modern": [
        {"key": "inland_hub", "name": "内陆枢纽城", "description": "承接产业转移的省会节点。"},
        {"key": "port_belt", "name": "临港产业带", "description": "外贸与先进制造并重。"},
    ],
    "ancient": [
        {"key": "luoyang", "name": "洛阳", "description": "东都繁华，漕运枢纽。"},
        {"key": "yangzhou", "name": "扬州", "description": "盐商聚集，运河要冲。"},
    ],
    "wuxia": [
        {"key": "luoyang", "name": "洛阳", "description": "血染旧案的风眼之地。"},
    ],
    "scifi": [
        {"key": "orbital", "name": "轨道港", "description": "星际贸易中转与补给。"},
    ],
    "enterprise": [
        {"key": "capital_row", "name": "资本街", "description": "融资与并购的信息中心。"},
    ],
    "securities": [
        {"key": "financial_district", "name": "金融城", "description": "交易所与投行总部集群。"},
    ],
    "military": [
        {"key": "arsenal_town", "name": "军工镇", "description": "装备研发与后勤补给基地。"},
    ],
}


_SEED_COMPANY_EXTRAS: dict[str, list[dict[str, Any]]] = {
    "modern": [
        {"key": "metro_dev", "name": "都会建设集团", "sector": "基建", "description": "城市更新与园区开发。"},
        {"key": "river_bank", "name": "滨河商业银行", "sector": "金融", "description": "本地按揭与 SME 信贷。"},
    ],
    "enterprise": [
        {"key": "rival_alpha", "name": "竞对 Alpha 科技", "sector": "SaaS", "description": "同赛道融资更快的挑战者。"},
        {"key": "supply_co", "name": "链合供应链", "sector": "供应链", "description": "关键零部件与履约。"},
    ],
    "securities": [
        {"key": "broker_x", "name": "远航证券", "sector": "券商", "description": "零售经纪与研究所。"},
        {"key": "asset_m", "name": "宏图资管", "sector": "资管", "description": "主动权益与量化产品。"},
    ],
    "wuxia": [
        {"key": "escort_union", "name": "天下镖局联盟", "sector": "物流", "description": "跨江湖货运与押运。"},
    ],
    "ancient": [
        {"key": "salt_guild", "name": "两淮盐商公会", "sector": "盐铁", "description": "专卖与漕运利益共同体。"},
    ],
}


ENTITY_ENTERPRISE = "enterprise"
ENTITY_UNIT = "unit"
ENTITY_PERSON = "person"

_ENTITY_LABELS = {
    ENTITY_ENTERPRISE: "企业",
    ENTITY_UNIT: "单位",
    ENTITY_PERSON: "自然人",
}

# Role / title markers — NPCs with these are natural persons, not corporate targets.
_PERSON_ROLE_MARKERS = (
    "引魂人", "首座", "弟子", "长老", "掌门", "真人", "剑客", "杀手", "侦探",
    "巡捕", "剑修", "修士", "镖师", "少侠", "侠士", "散修", "经纪人", "探长",
    "掌柜兼", "执事", "护法", "圣女", "魔头", "妖王", "少庄主", "行首", "账房",
    "守门", "艄公", "说书人", "掌柜", "僧", "鬼修", "狐", "客",
)

_ORG_MARKERS = ("宗", "帮", "堂", "庄", "局", "盟", "司", "行", "坊", "商号", "公司", "集团", "银行", "镖局")


def _entity_row(
    *,
    key: str,
    name: str,
    entity_type: str,
    seed_key: str,
    sector: str,
    description: str = "",
    base_lo: float = 40.0,
    base_hi: float = 180.0,
) -> dict[str, Any]:
    return {
        "key": key,
        "name": name[:24],
        "entity_type": entity_type,
        "entity_type_label": _ENTITY_LABELS.get(entity_type, entity_type),
        "sector": sector,
        "description": description[:120],
        "base_price": _base_price(seed_key, key, base_lo, base_hi),
    }


def _classify_npc(npc: dict[str, Any]) -> str:
    name = str(npc.get("name") or "").strip()
    profession = str(npc.get("profession") or "").strip()
    text = f"{name} {profession}"
    if profession and any(m in profession for m in _ORG_MARKERS) and not any(
        m in profession for m in _PERSON_ROLE_MARKERS
    ):
        return ENTITY_UNIT if len(profession) <= 14 else ENTITY_ENTERPRISE
    if any(m in text for m in _PERSON_ROLE_MARKERS):
        return ENTITY_PERSON
    if "·" in name and len(name) <= 12:
        return ENTITY_PERSON
    return ENTITY_PERSON


def _flagship_company(seed_key: str, seed_name: str, genre: str) -> dict[str, Any] | None:
    label = seed_name.split("·")[0].strip() or seed_name
    if not label or len(label) < 2:
        return None
    suffix = {
        "enterprise": "科技",
        "securities": "资本",
        "military": "工业",
        "modern": "控股",
    }.get(genre, "商号")
    name = f"{label}{suffix}"[:20]
    key = _slug(f"flagship:{seed_key}")
    return _entity_row(
        key=key,
        name=name,
        entity_type=ENTITY_ENTERPRISE,
        seed_key=seed_key,
        sector=_SECTOR_BY_GENRE.get(genre, "工商"),
        description=f"{seed_name} 文明下的代表性企业。",
        base_lo=80.0,
        base_hi=140.0,
    )


def _faction_to_company(fac: dict[str, Any], seed_key: str, genre: str) -> dict[str, Any] | None:
    name = str(fac.get("name") or "").strip()
    if not name or len(name) < 2:
        return None
    key = _slug(f"faction:{name}")
    return _entity_row(
        key=key,
        name=name[:24],
        entity_type=ENTITY_UNIT,
        seed_key=seed_key,
        sector=_infer_sector(name, genre),
        description=str(fac.get("ideology") or ""),
    )


def _npc_to_entity(npc: dict[str, Any], seed_key: str, genre: str) -> dict[str, Any] | None:
    name = str(npc.get("name") or "").strip()
    profession = str(npc.get("profession") or "").strip()
    if not name:
        return None
    entity_type = _classify_npc(npc)
    if entity_type == ENTITY_PERSON:
        return _entity_row(
            key=_slug(f"person:{name}"),
            name=name[:24],
            entity_type=ENTITY_PERSON,
            seed_key=seed_key,
            sector=profession[:24] or "个人",
            description=str(npc.get("persona") or ""),
            base_lo=0.0,
            base_hi=0.0,
        )
    comp_name = profession[:20] if len(profession) >= 4 and profession not in name else f"{name}系"[:20]
    return _entity_row(
        key=_slug(f"npc:{name}"),
        name=comp_name,
        entity_type=entity_type,
        seed_key=seed_key,
        sector=_infer_sector(profession or name, genre),
        description=str(npc.get("persona") or ""),
        base_lo=35.0,
        base_hi=120.0,
    )


def get_finance_cities(seed_key: str, user_id: str | None = None) -> list[dict[str, Any]]:
    seed = load_seed_any(seed_key, user_id=user_id)
    cities: list[dict[str, Any]] = []
    seen: set[str] = set()
    seen_names: set[str] = set()

    for loc in seed.locations or []:
        c = _city_from_location(loc)
        if c and c["key"] not in seen:
            cities.append(c)
            seen.add(c["key"])
            seen_names.add(c["name"])

    for extra in _SEED_CITY_EXTRAS.get(seed_key, []):
        if extra["key"] not in seen and extra.get("name") not in seen_names:
            cities.append(dict(extra))
            seen.add(extra["key"])
            seen_names.add(str(extra.get("name")))

    if not cities:
        label = (seed.name.split("·")[0] if seed.name else "本境")[:20]
        cities.append({
            "key": "default",
            "name": label or "本城",
            "description": seed.premise[:80] if seed.premise else "",
        })
    return cities[:8]


def get_finance_entities_all(seed_key: str, user_id: str | None = None) -> list[dict[str, Any]]:
    """All finance entities: enterprises, units, and natural persons."""
    seed = load_seed_any(seed_key, user_id=user_id)
    entities: list[dict[str, Any]] = []
    seen: set[str] = set()

    flagship = _flagship_company(seed_key, seed.name, seed.genre)
    if flagship:
        entities.append(flagship)
        seen.add(flagship["key"])

    for fac in seed.factions or []:
        c = _faction_to_company(fac, seed_key, seed.genre)
        if c and c["key"] not in seen:
            entities.append(c)
            seen.add(c["key"])

    for npc in (seed.npc_archetypes or [])[:8]:
        c = _npc_to_entity(npc, seed_key, seed.genre)
        if c and c["key"] not in seen:
            entities.append(c)
            seen.add(c["key"])

    for extra in _SEED_COMPANY_EXTRAS.get(seed_key, []):
        if extra["key"] not in seen:
            row = _entity_row(
                key=extra["key"],
                name=str(extra.get("name") or extra["key"]),
                entity_type=str(extra.get("entity_type") or ENTITY_ENTERPRISE),
                seed_key=seed_key,
                sector=str(extra.get("sector") or _SECTOR_BY_GENRE.get(seed.genre, "工商")),
                description=str(extra.get("description") or ""),
            )
            entities.append(row)
            seen.add(extra["key"])

    corporate = [e for e in entities if e.get("entity_type") != ENTITY_PERSON]
    if len(corporate) < 3:
        for i, (label, etype) in enumerate([
            ("甲号商号", ENTITY_ENTERPRISE),
            ("乙号工坊", ENTITY_ENTERPRISE),
            ("丙号行会", ENTITY_UNIT),
        ]):
            key = f"fallback_{i}"
            if key not in seen:
                entities.append(_entity_row(
                    key=key,
                    name=label,
                    entity_type=etype,
                    seed_key=seed_key,
                    sector=_SECTOR_BY_GENRE.get(seed.genre, "工商"),
                    description="文明沙盘合成主体。",
                    base_lo=50.0,
                    base_hi=90.0,
                ))
                seen.add(key)

    return entities[:12]


def get_finance_companies(seed_key: str, user_id: str | None = None) -> list[dict[str, Any]]:
    """Corporate evaluation targets — enterprises and units only (no natural persons)."""
    return [
        e for e in get_finance_entities_all(seed_key, user_id=user_id)
        if e.get("entity_type") in (ENTITY_ENTERPRISE, ENTITY_UNIT)
    ][:8]


def get_finance_entities(seed_key: str, user_id: str | None = None) -> dict[str, Any]:
    all_rows = get_finance_entities_all(seed_key, user_id=user_id)
    return {
        "cities": get_finance_cities(seed_key, user_id=user_id),
        "companies": get_finance_companies(seed_key, user_id=user_id),
        "persons": [e for e in all_rows if e.get("entity_type") == ENTITY_PERSON],
    }
