"""Civilization-scoped military scenarios — wars, campaigns, battles, guerrilla."""
from __future__ import annotations

import hashlib
from typing import Any

from ..layer2_civilization.civilization_resolver import load_seed_any

_SCENARIO_TYPES = {
    "war": "全面战争",
    "campaign": "战役",
    "battle": "集团作战",
    "guerrilla": "游击战",
    "assassination": "暗杀行动",
}

# genre / seed allowlists — scenarios only appear for matching civilizations
_ALL_SCENARIOS: list[dict[str, Any]] = [
    {"key": "spring_autumn", "name": "春秋诸侯争霸", "era": "前770–前221", "type": "war",
     "genres": [], "seed_keys": [],
     "red": "诸侯联军", "blue": "强权诸侯", "red_base": 0.52, "blue_base": 0.48},
    {"key": "han_xiongnu", "name": "汉匈漠北决战", "era": "前133–前89", "type": "campaign",
     "genres": [], "seed_keys": [],
     "red": "汉军", "blue": "匈奴", "red_base": 0.55, "blue_base": 0.45},
    {"key": "three_kingdoms", "name": "三国赤壁之战", "era": "208", "type": "battle",
     "genres": ["wuxia"], "seed_keys": [],
     "red": "孙刘联盟", "blue": "曹魏", "red_base": 0.50, "blue_base": 0.50},
    {"key": "yonghe_frontier", "name": "河陇边疆局部战", "era": "永和元年", "type": "campaign",
     "genres": [], "seed_keys": ["ancient"],
     "red": "边军戍卒", "blue": "北方部族", "red_base": 0.52, "blue_base": 0.48},
    {"key": "yonghe_fan", "name": "河朔藩镇对峙", "era": "永和元年", "type": "battle",
     "genres": [], "seed_keys": ["ancient"],
     "red": "朝廷平叛军", "blue": "河朔藩镇", "red_base": 0.48, "blue_base": 0.52},
    {"key": "yonghe_changan", "name": "长安地下密谋", "era": "永和元年", "type": "assassination",
     "genres": [], "seed_keys": ["ancient"],
     "red": "御史台暗线", "blue": "金乌社", "red_base": 0.46, "blue_base": 0.54},
    {"key": "yonghe_uprising", "name": "民变烽起游击", "era": "永和初年", "type": "guerrilla",
     "genres": [], "seed_keys": ["ancient"],
     "red": "地方守军", "blue": "饥民义军", "red_base": 0.50, "blue_base": 0.50},
    {"key": "jianghu_sect", "name": "江湖门派之争", "era": "风波渡", "type": "battle",
     "genres": ["wuxia"], "seed_keys": ["wuxia"],
     "red": "藏剑山庄", "blue": "血手堂", "red_base": 0.52, "blue_base": 0.48},
    {"key": "du_kou_ambush", "name": "渡口遭遇战", "era": "风波渡", "type": "guerrilla",
     "genres": ["wuxia"], "seed_keys": ["wuxia"],
     "red": "丐帮北分舵", "blue": "不明剑客", "red_base": 0.50, "blue_base": 0.50},
    {"key": "luoyang_inquiry", "name": "洛阳血案追缉", "era": "江湖", "type": "assassination",
     "genres": ["wuxia"], "seed_keys": ["wuxia"],
     "red": "追查者", "blue": "隐伏杀手", "red_base": 0.46, "blue_base": 0.54},
    {"key": "sect_war", "name": "宗门大会决战", "era": "九霄", "type": "war",
     "genres": ["xuanhuan"], "seed_keys": ["xuanhuan"],
     "red": "青云宗", "blue": "魔道联军", "red_base": 0.51, "blue_base": 0.49},
    {"key": "rift_defense", "name": "裂空防线阻击战", "era": "北域", "type": "campaign",
     "genres": ["xuanhuan"], "seed_keys": ["xuanhuan"],
     "red": "九霄守军", "blue": "裂空异族", "red_base": 0.47, "blue_base": 0.53},
    {"key": "underworld_raid", "name": "幽冥渡夜袭", "era": "幽冥", "type": "guerrilla",
     "genres": ["xuanhuan"], "seed_keys": ["xuanhuan"],
     "red": "宗门弟子", "blue": "幽冥渡守军", "red_base": 0.49, "blue_base": 0.51},
    {"key": "fog_port_gang", "name": "雾港帮派火并", "era": "1931", "type": "battle",
     "genres": ["mystery"], "seed_keys": ["mystery"],
     "red": "巡捕房", "blue": "青莲会", "red_base": 0.50, "blue_base": 0.50},
    {"key": "warehouse_hit", "name": "七号仓库暗杀", "era": "1931", "type": "assassination",
     "genres": ["mystery"], "seed_keys": ["mystery"],
     "red": "调查方", "blue": "灭口者", "red_base": 0.45, "blue_base": 0.55},
    {"key": "orbital_battle", "name": "轨道舰队会战", "era": "星际", "type": "war",
     "genres": ["scifi"], "seed_keys": ["scifi"],
     "red": "联邦舰队", "blue": "分离势力", "red_base": 0.52, "blue_base": 0.48},
    {"key": "station_raid", "name": "空间站夺控", "era": "近轨", "type": "campaign",
     "genres": ["scifi"], "seed_keys": ["scifi"],
     "red": "突击编队", "blue": "守备军", "red_base": 0.48, "blue_base": 0.52},
    {"key": "urban_ct", "name": "城市反恐行动", "era": "当代", "type": "campaign",
     "genres": ["modern"], "seed_keys": ["modern"],
     "red": "特勤联队", "blue": "武装团伙", "red_base": 0.56, "blue_base": 0.44},
    {"key": "industrial_unrest", "name": "产业区对峙", "era": "当代", "type": "battle",
     "genres": [], "seed_keys": ["modern", "enterprise"],
     "red": "市政安保", "blue": "激进群体", "red_base": 0.54, "blue_base": 0.46},
    {"key": "border_standoff", "name": "边境对峙推演", "era": "当代", "type": "campaign",
     "genres": ["military"], "seed_keys": ["military"],
     "red": "守备部队", "blue": "对手集团军", "red_base": 0.50, "blue_base": 0.50},
    {"key": "gulf_strike", "name": "沙漠风暴战役", "era": "1991", "type": "war",
     "genres": ["military"], "seed_keys": ["military"],
     "red": "多国联军", "blue": "守方", "red_base": 0.62, "blue_base": 0.38},
    {"key": "market_raid", "name": "资本市场攻防", "era": "当代", "type": "battle",
     "genres": ["securities", "enterprise"], "seed_keys": ["securities", "enterprise"],
     "red": "多头联盟", "blue": "空头阵营", "red_base": 0.50, "blue_base": 0.50},
    {"key": "ww2_europe", "name": "诺曼底登陆", "era": "1944", "type": "campaign",
     "genres": [], "seed_keys": ["military"],
     "red": "盟军", "blue": "德军", "red_base": 0.48, "blue_base": 0.52},
    {"key": "russia_ukraine", "name": "俄乌阵地战", "era": "2022–", "type": "war",
     "genres": [], "seed_keys": ["military"],
     "red": "守势一方", "blue": "攻势一方", "red_base": 0.46, "blue_base": 0.54},
]


def _slug(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:10]


def _match_scenario(sc: dict[str, Any], seed_key: str, genre: str) -> bool:
    seed_keys = sc.get("seed_keys") or []
    genres = sc.get("genres") or []
    if seed_keys:
        return seed_key in seed_keys
    if seed_key.startswith("custom_"):
        return sc.get("type") in ("battle", "campaign", "guerrilla", "assassination")
    if genres:
        return genre in genres
    return False


def _dynamic_scenarios(seed_key: str, seed: Any) -> list[dict[str, Any]]:
    dynamic: list[dict[str, Any]] = []
    factions = seed.factions or []
    if len(factions) >= 2:
        a, b = factions[0], factions[1]
        an, bn = str(a.get("name", "甲")), str(b.get("name", "乙"))
        dynamic.append({
            "key": f"dyn_{_slug(an + bn)}",
            "name": f"{an} vs {bn}",
            "era": seed.name.split("·")[-1] if seed.name else "本文明",
            "type": "campaign",
            "type_label": _SCENARIO_TYPES["campaign"],
            "red": an[:16],
            "blue": bn[:16],
            "red_base": 0.50,
            "blue_base": 0.50,
            "dynamic": True,
        })
    if len(factions) >= 3:
        c = factions[2]
        cn = str(c.get("name", "丙"))
        dynamic.append({
            "key": f"dyn_guerrilla_{_slug(cn)}",
            "name": f"{cn}游击袭扰",
            "era": seed.name or "",
            "type": "guerrilla",
            "type_label": _SCENARIO_TYPES["guerrilla"],
            "red": str(factions[0].get("name", "红方"))[:16],
            "blue": cn[:16],
            "red_base": 0.52,
            "blue_base": 0.48,
            "dynamic": True,
        })
    if seed_key.startswith("custom_"):
        dynamic.insert(0, {
            "key": "custom_defense",
            "name": f"{seed.name or '自定义文明'}保卫战",
            "era": "自定义",
            "type": "war",
            "type_label": _SCENARIO_TYPES["war"],
            "red": (seed.name or "守方")[:16],
            "blue": "外敌/intervention",
            "red_base": 0.50,
            "blue_base": 0.50,
            "dynamic": True,
        })
    return dynamic


def get_military_scenarios(seed_key: str, user_id: str | None = None) -> list[dict[str, Any]]:
    seed = load_seed_any(seed_key, user_id=user_id)
    genre = seed.genre or "ancient"
    seen: set[str] = set()
    out: list[dict[str, Any]] = []

    for sc in _dynamic_scenarios(seed_key, seed):
        if sc["key"] not in seen:
            row = dict(sc)
            row.setdefault("type_label", _SCENARIO_TYPES.get(row["type"], row["type"]))
            out.append(row)
            seen.add(sc["key"])

    for sc in _ALL_SCENARIOS:
        if not _match_scenario(sc, seed_key, genre):
            continue
        if sc["key"] in seen:
            continue
        row = {k: v for k, v in sc.items() if k not in ("genres", "seed_keys")}
        row["type_label"] = _SCENARIO_TYPES.get(row.get("type", ""), row.get("type", ""))
        out.append(row)
        seen.add(sc["key"])

    if not out:
        out.append({
            "key": "fallback_battle",
            "name": f"{seed.name or '本文明'}遭遇战",
            "era": "—",
            "type": "battle",
            "type_label": _SCENARIO_TYPES["battle"],
            "red": "红方", "blue": "蓝方",
            "red_base": 0.50, "blue_base": 0.50,
        })
    return out[:12]


def scenario_by_key(scenarios: list[dict[str, Any]], key: str) -> dict[str, Any]:
    return next((s for s in scenarios if s["key"] == key), scenarios[0])
