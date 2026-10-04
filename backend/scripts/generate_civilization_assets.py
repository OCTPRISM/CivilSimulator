#!/usr/bin/env python3
"""Generate per-civilization 3D characters, outfit metadata, and selectable prop GLBs.

Output layout:
  frontend/public/models/characters/civilizations/{civ}/
    catalog.json
    character/body.glb + skins/{fair|tan|warm|pale}/
    outfits/{outfit_id}/meta.json
    props/{prop_slug}/prop.glb

Also mirrors catalog into:
  backend/data/runtime/generator/civilizations/{civ}/catalog.json

Usage:
  python3 backend/scripts/generate_civilization_assets.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.generator.outfits import (  # noqa: E402
    CIVILIZATION_OUTFITS,
    CIV_META,
    DEFAULT_ROLE,
    MESH_GENRE,
    _slug,
    list_civilizations,
    list_outfits,
)

# Reuse procedural mesh helpers
sys.path.insert(0, str(ROOT / "backend" / "scripts"))
from generate_role_bodies import (  # noqa: E402
    MeshBuf,
    ROLE_COLORS,
    SKIN_NAMES,
    build_humanoid,
    gen_skin_pack,
    write_glb,
)

OUT = ROOT / "frontend" / "public" / "models" / "characters" / "civilizations"
RUNTIME = ROOT / "backend" / "data" / "runtime" / "generator" / "civilizations"


def _prop_mesh(name: str, seed: int) -> tuple[dict[str, MeshBuf], dict]:
    """Simple distinct prop silhouettes for selectable items."""
    metal = MeshBuf()
    cloth = MeshBuf()
    skin = MeshBuf()
    hair = MeshBuf()
    eye = MeshBuf()
    n = name.lower()
    h = (seed % 97) / 97.0

    if any(k in n for k in ("剑", "刀", "戟", "枪", "步枪", "焊枪")):
        metal.add_box(0, 0.55, 0, 0.04, 1.1, 0.08)
        metal.add_box(0, 0.05, 0, 0.14, 0.08, 0.1)
        metal.add_box(0, -0.08, 0, 0.05, 0.16, 0.05)
    elif any(k in n for k in ("弓", "箭")):
        metal.add_cyl(0, 0.4, 0, 0.02, 0.02, 0.9, segs=8)
        cloth.add_box(0.12, 0.4, 0, 0.04, 0.5, 0.04)
        metal.add_box(-0.05, 0.2, 0.1, 0.2, 0.25, 0.08)  # quiver
    elif any(k in n for k in ("书", "账", "报", "草稿", "清单", "手册", "材料", "夹")):
        cloth.add_box(0, 0.15, 0, 0.28, 0.06, 0.36)
        cloth.add_box(0, 0.19, 0, 0.26, 0.02, 0.34)
    elif any(k in n for k in ("笔", "扇", "笛", "针", "钥", "卡", "牌", "令", "证")):
        metal.add_cyl(0, 0.2, 0, 0.015, 0.012, 0.45, segs=8)
        cloth.add_box(0, 0.42, 0, 0.06, 0.04, 0.04)
    elif any(k in n for k in ("箱", "囊", "袋", "包", "炉", "机", "屏", "板", "端", "仪", "设备")):
        cloth.add_box(0, 0.2, 0, 0.35 + 0.05 * h, 0.28, 0.22)
        metal.add_box(0, 0.36, 0.05, 0.2, 0.04, 0.08)
    elif any(k in n for k in ("相机", "手机", "平板", "电脑", "笔记本", "终端")):
        metal.add_box(0, 0.18, 0, 0.32, 0.04, 0.22)
        cloth.add_box(0, 0.2, 0.01, 0.28, 0.01, 0.18)
    elif any(k in n for k in ("葫芦", "碗", "杯", "饮料")):
        cloth.add_sphere(0, 0.22, 0, 0.12)
        cloth.add_cyl(0, 0.34, 0, 0.04, 0.05, 0.1, segs=8)
    elif any(k in n for k in ("帽", "盔")):
        cloth.add_cyl(0, 0.15, 0, 0.16, 0.12, 0.12, segs=12)
        cloth.add_box(0, 0.1, 0, 0.36, 0.03, 0.36)
    else:
        # generic tricube
        cloth.add_box(0, 0.15, 0, 0.22, 0.22, 0.22)
        metal.add_box(0, 0.28, 0, 0.1, 0.08, 0.1)

    colors = {
        "Skin": (0.85, 0.7, 0.55),
        "Cloth": (0.35 + 0.2 * h, 0.32, 0.28),
        "Metal": (0.65, 0.68, 0.72),
        "Hair": (0.1, 0.1, 0.1),
        "Eye": (0.1, 0.12, 0.2),
    }
    return {"Skin": skin, "Cloth": cloth, "Metal": metal, "Hair": hair, "Eye": eye}, colors


def _write_character(civ: str, role_id: str, genre: str, seed: int) -> dict:
    char_dir = OUT / civ / "character"
    char_dir.mkdir(parents=True, exist_ok=True)
    parts, colors = build_humanoid(genre, role_id, seed=seed)
    # Prefer palette if known
    if role_id in ROLE_COLORS:
        colors.update({k: ROLE_COLORS[role_id][k] for k in ROLE_COLORS[role_id]})
    write_glb(char_dir / "body.glb", parts, colors)
    for skin in SKIN_NAMES:
        gen_skin_pack(char_dir, skin)
    return {
        "role_id": role_id,
        "body": f"/models/characters/civilizations/{civ}/character/body.glb",
        "skins": [
            {
                "id": s,
                "map": f"/models/characters/civilizations/{civ}/character/skins/{s}/albedo.png",
                "roughnessMap": f"/models/characters/civilizations/{civ}/character/skins/{s}/roughness.png",
                "normalMap": f"/models/characters/civilizations/{civ}/character/skins/{s}/normal.png",
                "metalnessMap": f"/models/characters/civilizations/{civ}/character/skins/{s}/metalness.png",
            }
            for s in SKIN_NAMES
        ],
    }


def generate_civ(civ: str) -> dict:
    meta = CIV_META[civ]
    genre = MESH_GENRE[civ]
    role_id = DEFAULT_ROLE[civ]
    outfits = list_outfits(civ)

    civ_dir = OUT / civ
    civ_dir.mkdir(parents=True, exist_ok=True)
    (civ_dir / "outfits").mkdir(exist_ok=True)
    (civ_dir / "props").mkdir(exist_ok=True)

    character = _write_character(civ, role_id, genre, seed=2000 + abs(hash(civ)) % 5000)

    outfit_entries = []
    prop_index: dict[str, str] = {}
    for i, o in enumerate(outfits):
        oid = o["id"]
        odir = civ_dir / "outfits" / oid
        odir.mkdir(parents=True, exist_ok=True)
        prop_paths = []
        for j, pname in enumerate(o.get("props", [])):
            slug = _slug(pname)
            pdir = civ_dir / "props" / slug
            pdir.mkdir(parents=True, exist_ok=True)
            glb = pdir / "prop.glb"
            if not glb.is_file():
                parts, colors = _prop_mesh(pname, seed=3000 + i * 17 + j * 3)
                write_glb(glb, parts, colors)
            url = f"/models/characters/civilizations/{civ}/props/{slug}/prop.glb"
            prop_index[slug] = url
            prop_paths.append({"name": pname, "slug": slug, "glb": url})

        entry = {
            "id": oid,
            "label": o["label"],
            "occupation": o["occupation"],
            "blurb": o["blurb"],
            "clothing": o["clothing"],
            "props": o["props"],
            "prompt": o["prompt"],
            "role_hint": o.get("role_hint"),
            "props_assets": prop_paths,
        }
        (odir / "meta.json").write_text(
            json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        outfit_entries.append({
            **entry,
            "meta_url": f"/models/characters/civilizations/{civ}/outfits/{oid}/meta.json",
        })

    catalog = {
        "id": civ,
        "name": meta["name"],
        "genre": meta["genre"],
        "era": meta["era"],
        "mesh_genre": genre,
        "character": character,
        "outfits": outfit_entries,
        "props": [{"slug": k, "glb": v} for k, v in sorted(prop_index.items())],
    }
    (civ_dir / "catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Runtime mirror (generator jobs / offline index)
    rdir = RUNTIME / civ
    rdir.mkdir(parents=True, exist_ok=True)
    (rdir / "catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return catalog


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    RUNTIME.mkdir(parents=True, exist_ok=True)
    index = []
    for civ in CIV_META:
        cat = generate_civ(civ)
        index.append({
            "id": civ,
            "name": cat["name"],
            "era": cat["era"],
            "outfit_count": len(cat["outfits"]),
            "prop_count": len(cat["props"]),
            "catalog_url": f"/models/characters/civilizations/{civ}/catalog.json",
            "character_url": cat["character"]["body"],
        })
        print(f"ok {civ}: {len(cat['outfits'])} outfits, {len(cat['props'])} props")

    (OUT / "index.json").write_text(
        json.dumps({"civilizations": index}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RUNTIME / "index.json").write_text(
        json.dumps({"civilizations": index}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"wrote {len(index)} civilizations → {OUT}")


if __name__ == "__main__":
    main()
