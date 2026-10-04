"""Per-civilization map briefs — story-aligned prompts + visual DNA for HunyuanDiT."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SEEDS_DIR = Path(__file__).resolve().parents[1] / "seeds"

# Visual DNA: must differ across civs (area scale, relief, water, vegetation, palette)
MAP_DNA: dict[str, dict[str, Any]] = {
    "ancient": {
        "shape": "river_plains",
        "world_scale": 1.35,
        "max_height": 28,
        "water_level": -0.34,
        "vegetation": "稻田与稀疏柏树、护城河",
        "palette": "土黄城垣、青绿稻田、灰蓝渭水",
        "dit_style": "唐代帝都俯瞰图, fort walls, palace north, markets south, river plains, ink wash with soft color",
    },
    "wuxia": {
        "shape": "rivers_and_peaks",
        "world_scale": 1.15,
        "max_height": 32,
        "water_level": -0.26,
        "vegetation": "密林竹海、江岸芦苇",
        "palette": "黛绿群山、赤霞江面、雾白",
        "dit_style": "武侠江河峡谷俯瞰, ferry crossing, mountain mist, bamboo forests, cinematic wuxia landscape",
    },
    "xuanhuan": {
        "shape": "floating_isles",
        "world_scale": 1.55,
        "max_height": 38,
        "water_level": -0.48,
        "vegetation": "紫冠灵木、云海断崖",
        "palette": "紫金云海、青白峰峦、星裂紫光",
        "dit_style": "玄幻仙山俯瞰, floating peaks above clouds, spirit market below, purple canopy, epic fantasy map",
    },
    "mystery": {
        "shape": "fog_harbor",
        "world_scale": 0.92,
        "max_height": 18,
        "water_level": -0.12,
        "vegetation": "稀少芦苇、湿冷码头",
        "palette": "煤灰街道、墨绿海水、昏黄灯火",
        "dit_style": "1931雾港俯瞰, noir harbor, warehouses, art deco ballroom hill, thick fog, muted sepia teal",
    },
    "modern": {
        "shape": "city_grid",
        "world_scale": 1.0,
        "max_height": 16,
        "water_level": -0.38,
        "vegetation": "滨河公园带、行道树",
        "palette": "玻璃蓝、沥青灰、夜市暖光",
        "dit_style": "contemporary coastal metropolis top-down, CBD towers, civic hall, riverside night market, clear daylight",
    },
    "scifi": {
        "shape": "orbital_hub",
        "world_scale": 1.25,
        "max_height": 24,
        "water_level": -0.55,
        "vegetation": "极少; 冷却液渠与金属苔",
        "palette": "青霓虹、深空黑、银灰甲",
        "dit_style": "Saturn ring colony top-down, orbital hub, neon pathways, docking pads, starfield, sci-fi schematic beauty",
    },
    "enterprise": {
        "shape": "campus_plateau",
        "world_scale": 0.88,
        "max_height": 14,
        "water_level": -0.4,
        "vegetation": "草坪广场、玻璃中庭绿植",
        "palette": "玻璃青绿、清水混凝土、路演暖白",
        "dit_style": "tech campus aerial map, coworking towers, capital street pitch hall, lawn plazas, clean glass teal",
    },
    "securities": {
        "shape": "lake_finance",
        "world_scale": 0.85,
        "max_height": 12,
        "water_level": -0.08,
        "vegetation": "几何灌木、湖滨步道",
        "palette": "冷灰蓝、镜面湖、交易所金",
        "dit_style": "lakeside financial district aerial, exchange hall, broker towers, reflective lake, cool blue-gray",
    },
    "military": {
        "shape": "canyon_front",
        "world_scale": 1.45,
        "max_height": 36,
        "water_level": -0.45,
        "vegetation": "山脊灌丛与稀疏松",
        "palette": "土黄尘、橄榄迷彩、补给灰",
        "dit_style": "military canyon front aerial map, ridge outposts, logistics yard, supply corridor, dust olive khaki",
    },
}


def load_seed(civ: str) -> dict[str, Any]:
    p = SEEDS_DIR / f"{civ}.json"
    if not p.is_file():
        return {"key": civ, "name": civ, "premise": "", "locations": []}
    return json.loads(p.read_text(encoding="utf-8"))


def map_brief(civ: str) -> dict[str, Any]:
    seed = load_seed(civ)
    dna = MAP_DNA.get(civ, MAP_DNA["modern"])
    locs = seed.get("locations") or []
    loc_names = [l.get("name", "") for l in locs[:5] if isinstance(l, dict)]
    premise = (seed.get("premise") or "")[:120]
    places = "、".join(loc_names) if loc_names else civ
    dit_prompt = (
        f"鸟瞰战略地图,俯视全图,{seed.get('name', civ)},{premise},"
        f"地标:{places},面积尺度{dna['world_scale']},"
        f"地势高度差明显,植被:{dna['vegetation']},色调:{dna['palette']},"
        f"{dna['dit_style']},无文字水印,干净构图,游戏概念地图"
    )
    return {
        "civilization": civ,
        "name": seed.get("name", civ),
        "premise": premise,
        "locations": loc_names,
        "dna": dna,
        "dit_prompt": dit_prompt,
    }


def list_map_briefs() -> list[dict[str, Any]]:
    return [map_brief(k) for k in MAP_DNA]


def paint_style_for(civ: str) -> dict[str, Any]:
    """Pillow fallback palette keyed by civ (used if DiT offline)."""
    dna = MAP_DNA[civ]
    palettes = {
        "ancient": dict(sky=(60, 50, 40), land_low=(90, 76, 52), land_hi=(140, 120, 86), water=(52, 76, 96), road=(180, 156, 110), accent=(220, 190, 120), label=(240, 224, 180)),
        "wuxia": dict(sky=(38, 32, 44), land_low=(62, 80, 64), land_hi=(124, 152, 110), water=(60, 84, 110), road=(200, 170, 110), accent=(244, 196, 124), label=(240, 220, 196)),
        "xuanhuan": dict(sky=(24, 18, 48), land_low=(60, 40, 92), land_hi=(120, 78, 168), water=(48, 30, 92), road=(236, 200, 255), accent=(250, 210, 130), label=(240, 224, 255)),
        "mystery": dict(sky=(45, 48, 55), land_low=(70, 72, 68), land_hi=(110, 108, 95), water=(30, 55, 70), road=(40, 42, 45), accent=(200, 170, 90), label=(230, 220, 200)),
        "modern": dict(sky=(72, 110, 148), land_low=(88, 98, 78), land_hi=(130, 138, 108), water=(40, 96, 128), road=(55, 58, 62), accent=(250, 210, 90), label=(250, 250, 252)),
        "scifi": dict(sky=(8, 16, 28), land_low=(24, 44, 60), land_hi=(60, 110, 150), water=(8, 24, 40), road=(120, 220, 240), accent=(120, 220, 240), label=(220, 240, 255)),
        "enterprise": dict(sky=(200, 220, 230), land_low=(140, 160, 150), land_hi=(190, 210, 200), water=(90, 150, 160), road=(120, 125, 130), accent=(40, 160, 170), label=(30, 50, 60)),
        "securities": dict(sky=(55, 70, 90), land_low=(70, 80, 88), land_hi=(120, 130, 140), water=(40, 90, 130), road=(50, 55, 60), accent=(212, 175, 55), label=(240, 245, 250)),
        "military": dict(sky=(90, 85, 70), land_low=(100, 95, 70), land_hi=(140, 125, 90), water=(70, 85, 75), road=(90, 85, 70), accent=(110, 130, 70), label=(230, 220, 190)),
    }
    st = palettes.get(civ, palettes["modern"]).copy()
    st["shape"] = dna["shape"]
    st["road_width"] = 5 if civ in ("modern", "enterprise", "securities") else (4 if civ == "scifi" else 3)
    return st
