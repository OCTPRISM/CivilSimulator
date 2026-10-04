"""Era-consistent population & civilization metrics per seed/custom config."""
from __future__ import annotations

from typing import Any

# Built-in civilization demographic profiles (self-consistent per era/scale)
_SEED_DEMOGRAPHICS: dict[str, dict[str, Any]] = {
    "ancient": {
        "era_label": "永和元年·唐中期",
        "year_abs": 806,
        "total_pop": 48_000_000,
        "urban_pop_pct": 0.11,
        "literacy_pct": 0.05,
        "life_expectancy": 42,
        "fertility_rate": 4.2,
        "gdp_index": 100,
        "explanation": "王朝鼎盛后期，户籍约四千八百万，长安洛阳为核心都市，农耕为主。",
    },
    "wuxia": {
        "era_label": "江湖·风波渡周边",
        "year_abs": 1520,
        "total_pop": 2_800_000,
        "urban_pop_pct": 0.18,
        "literacy_pct": 0.12,
        "life_expectancy": 38,
        "fertility_rate": 3.8,
        "gdp_index": 72,
        "explanation": "以风波渡为中心的江湖区域，人口约二百八十万，市镇与镖局聚落带动局部繁荣。",
    },
    "scifi": {
        "era_label": "环带殖民地·2387",
        "year_abs": 2387,
        "total_pop": 420_000,
        "urban_pop_pct": 0.92,
        "literacy_pct": 0.98,
        "life_expectancy": 88,
        "fertility_rate": 1.4,
        "gdp_index": 145,
        "explanation": "土星环带人类殖民地约四十二万，高度城市化，能源与算力驱动经济。",
    },
    "xuanhuan": {
        "era_label": "九霄大陆·灵气复苏千年",
        "year_abs": 0,
        "total_pop": 120_000_000,
        "urban_pop_pct": 0.22,
        "literacy_pct": 0.08,
        "life_expectancy": 55,
        "fertility_rate": 3.2,
        "gdp_index": 85,
        "explanation": "修真文明凡俗界约一亿二千万，修士占比极低但掌握资源分配。",
    },
    "mystery": {
        "era_label": "雾港·1931",
        "year_abs": 1931,
        "total_pop": 180_000,
        "urban_pop_pct": 0.95,
        "literacy_pct": 0.88,
        "life_expectancy": 58,
        "fertility_rate": 2.1,
        "gdp_index": 110,
        "explanation": "雾港港口城市约十八万人口，工业与航运业为主，大萧条阴影下。",
    },
    "modern": {
        "era_label": "当代·都会",
        "year_abs": 2026,
        "total_pop": 12_400_000,
        "urban_pop_pct": 0.89,
        "literacy_pct": 0.99,
        "life_expectancy": 79,
        "fertility_rate": 1.3,
        "gdp_index": 128,
        "explanation": "沿海特大城市圈约一千二百四十万，服务业与先进制造双轮驱动。",
    },
    "enterprise": {
        "era_label": "创业纪·2020s",
        "year_abs": 2024,
        "total_pop": 8_500_000,
        "urban_pop_pct": 0.91,
        "literacy_pct": 0.99,
        "life_expectancy": 78,
        "fertility_rate": 1.2,
        "gdp_index": 132,
        "explanation": "科创走廊城市约八百五十万，人才密度高，企业生态活跃。",
    },
    "securities": {
        "era_label": "镜湖交易日·2020s",
        "year_abs": 2025,
        "total_pop": 6_200_000,
        "urban_pop_pct": 0.94,
        "literacy_pct": 0.99,
        "life_expectancy": 80,
        "fertility_rate": 1.1,
        "gdp_index": 140,
        "explanation": "金融中心都市约六百二十万，金融与专业服务占 GDP 比重超四成。",
    },
    "military": {
        "era_label": "边关对峙·当代",
        "year_abs": 2026,
        "total_pop": 1_200_000,
        "urban_pop_pct": 0.35,
        "literacy_pct": 0.95,
        "life_expectancy": 72,
        "fertility_rate": 1.8,
        "gdp_index": 95,
        "explanation": "边境战区及周边约一百二十万，军民混居，补给枢纽城镇集中。",
    },
}


def get_demographics(civ_ctx: dict[str, Any]) -> dict[str, Any]:
    key = civ_ctx.get("key", "modern")
    genre = civ_ctx.get("genre", "modern")
    base = dict(_SEED_DEMOGRAPHICS.get(key) or _SEED_DEMOGRAPHICS.get(genre) or _SEED_DEMOGRAPHICS["modern"])

    if key.startswith("custom_") or genre == "custom":
        cls = civ_ctx.get("class_structure") or {}
        age = civ_ctx.get("age_structure") or {}
        ruling = float(cls.get("ruling", 0.05))
        labor = float(cls.get("labor", 0.5))
        elder = float(age.get("elder", 0.08))
        # Scale: more labor/agrarian → larger pop base; more ruling → smaller elite state
        scale = 800_000 + int(labor * 4_000_000) + int((1 - ruling) * 2_000_000)
        urban = min(0.95, 0.15 + ruling * 2 + float(cls.get("middle", 0.3)))
        fert = max(1.0, 4.5 - elder * 8 - urban * 2)
        base.update({
            "era_label": civ_ctx.get("current_stage") or "自定义文明",
            "total_pop": scale,
            "urban_pop_pct": round(urban, 3),
            "fertility_rate": round(fert, 2),
            "literacy_pct": round(0.1 + (1 - labor) * 0.5 + float(cls.get("middle", 0.3)) * 0.3, 3),
            "life_expectancy": int(38 + (1 - labor) * 25 + elder * 20),
            "explanation": (
                f"基于阶层结构（劳动阶层 {labor*100:.0f}%）与阶段「{civ_ctx.get('current_stage', '')}」"
                f"推算人口约 {scale:,}，城镇化 {urban*100:.0f}%。"
            ),
        })
    base["civilization_key"] = key
    base["civilization_name"] = civ_ctx.get("name", "")
    return base
