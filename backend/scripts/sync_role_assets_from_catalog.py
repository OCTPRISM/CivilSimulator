#!/usr/bin/env python3
"""Build CIVILIZATION_OUTFITS + role list from player_catalog.json (source of truth).

Run via generate_civilization_assets / generate_role_bodies after updating outfits.py.
This script prints the derived mapping and can rewrite outfits.py ROLE tables —
prefer editing player_catalog then syncing.

Usage (audit + emit patch data):
  python3 backend/scripts/sync_role_assets_from_catalog.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "backend" / "app" / "seeds" / "player_catalog.json"
SEEDS = ROOT / "backend" / "app" / "seeds"
ROLES_DIR = ROOT / "frontend" / "public" / "models" / "characters" / "roles"
CIVS_DIR = ROOT / "frontend" / "public" / "models" / "characters" / "civilizations"

MESH_GENRE = {
    "ancient": "ancient",
    "wuxia": "wuxia",
    "xuanhuan": "xuanhuan",
    "scifi": "scifi",
    "mystery": "mystery",
    "modern": "modern",
    "enterprise": "modern",
    "securities": "modern",
    "military": "scifi",
}


def _slug(name: str) -> str:
    s = "".join(ch if ch.isalnum() else "_" for ch in name.strip())
    while "__" in s:
        s = s.replace("__", "_")
    return s.strip("_").lower() or "prop"


def clothing_from_equipment(eq: dict) -> list[str]:
    keys = ("防具", "服饰", "外套", "衣", "袍", "装")
    out = []
    for k, v in eq.items():
        if any(x in k for x in keys) or any(x in str(v) for x in ("袍", "衣", "装", "甲", "衫", "服", "帽", "靴", "履")):
            out.append(str(v))
    return out or [str(v) for v in list(eq.values())[:2]]


def props_from_equipment(eq: dict) -> list[str]:
    clothish = set(clothing_from_equipment(eq))
    props = [str(v) for v in eq.values() if str(v) not in clothish]
    return props or [str(v) for v in eq.values()]


def prompt_for(seed: str, name: str, profession: str, clothing: list[str], props: list[str]) -> str:
    c = "、".join(clothing)
    p = "、".join(props)
    return f"{seed}风格角色,{name},{profession}装束,{c},手持或佩戴{p},全身站立,白色背景,3D风格"


def iter_variants(catalog: dict):
    for seed, data in catalog.items():
        for cat in data.get("categories", []):
            for v in cat.get("variants", []):
                yield seed, cat, v


def main() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    seed_names = {}
    for p in SEEDS.glob("*.json"):
        if p.name == "player_catalog.json":
            continue
        seed_names[p.stem] = json.loads(p.read_text(encoding="utf-8")).get("name", p.stem)

    # --- ensure every variant has body.glb ---
    import sys
    sys.path.insert(0, str(ROOT / "backend" / "scripts"))
    from generate_role_bodies import (  # type: ignore
        ROLE_COLORS,
        SKIN_NAMES,
        build_humanoid,
        gen_skin_pack,
        write_glb,
    )

    roles_needed = []
    outfits_by_civ: dict[str, list[dict]] = {k: [] for k in catalog}
    missing_bodies = []

    for seed, cat, v in iter_variants(catalog):
        role_id = f"{seed}_{v['key']}"
        roles_needed.append((MESH_GENRE.get(seed, "modern"), role_id))
        eq = v.get("equipment") or {}
        clothing = clothing_from_equipment(eq)
        props = props_from_equipment(eq)
        # if clothing empty, use profession as clothing tag
        if not clothing:
            clothing = [f"{v.get('profession', v['name'])}常服"]
        outfit = {
            "id": role_id,
            "label": v["name"],
            "occupation": v.get("profession") or cat.get("name") or v["name"],
            "blurb": (v.get("persona") or "")[:24],
            "clothing": clothing,
            "props": props,
            "prompt": prompt_for(seed, v["name"], v.get("profession") or "", clothing, props),
            "role_hint": role_id,
        }
        outfits_by_civ[seed].append(outfit)

        body = ROLES_DIR / role_id / "body.glb"
        if not body.is_file():
            missing_bodies.append(role_id)

    print(f"playable roles: {len(roles_needed)}")
    print(f"missing bodies before gen: {missing_bodies}")

    # generate missing (+ refresh all playable to be safe)
    ROLES_DIR.mkdir(parents=True, exist_ok=True)
    catalog_out = []
    for i, (genre, role_id) in enumerate(roles_needed):
        role_dir = ROLES_DIR / role_id
        parts, colors = build_humanoid(genre, role_id, seed=1000 + i * 97)
        if role_id in ROLE_COLORS:
            colors.update(ROLE_COLORS[role_id])
        write_glb(role_dir / "body.glb", parts, colors)
        for skin in SKIN_NAMES:
            gen_skin_pack(role_dir, skin)
        catalog_out.append({
            "id": role_id,
            "genre": genre,
            "body": f"/models/characters/roles/{role_id}/body.glb",
            "skins": [
                {
                    "id": s,
                    "map": f"/models/characters/roles/{role_id}/skins/{s}/albedo.png",
                    "roughnessMap": f"/models/characters/roles/{role_id}/skins/{s}/roughness.png",
                    "normalMap": f"/models/characters/roles/{role_id}/skins/{s}/normal.png",
                    "metalnessMap": f"/models/characters/roles/{role_id}/skins/{s}/metalness.png",
                }
                for s in SKIN_NAMES
            ],
        })
        print(f"role ok {role_id}")

    # keep npc_* entries from previous catalog if present
    prev = []
    prev_path = ROLES_DIR / "catalog.json"
    if prev_path.is_file():
        prev = [r for r in json.loads(prev_path.read_text()) if str(r.get("id", "")).startswith("npc_")]
    (ROLES_DIR / "catalog.json").write_text(
        json.dumps(catalog_out + prev, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # --- write per-civ catalogs with ALL role outfits + props ---
    # reuse prop mesh helper from civilization generator
    sys.path.insert(0, str(ROOT / "backend"))
    from scripts.generate_civilization_assets import _prop_mesh, _write_character  # type: ignore
    # import may fail due to package path — inline prop write
    from generate_role_bodies import write_glb as write_glb2  # noqa: F811

    def write_prop(path: Path, name: str, seed: int) -> None:
        # local copy of simple prop logic
        from generate_civilization_assets import _prop_mesh as pm
        parts, colors = pm(name, seed)
        write_glb2(path, parts, colors)

    index = []
    for seed, outfits in outfits_by_civ.items():
        meta_name = seed_names.get(seed, seed)
        genre = MESH_GENRE.get(seed, "modern")
        default_role = outfits[0]["role_hint"] if outfits else f"{seed}_default"

        civ_dir = CIVS_DIR / seed
        civ_dir.mkdir(parents=True, exist_ok=True)
        (civ_dir / "outfits").mkdir(exist_ok=True)
        (civ_dir / "props").mkdir(exist_ok=True)
        (civ_dir / "roles").mkdir(exist_ok=True)

        # civ hero character = first variant / preferred
        preferred = {
            "ancient": "ancient_student",
            "wuxia": "wuxia_wanderer",
            "xuanhuan": "xuanhuan_outer",
            "scifi": "scifi_scout",
            "mystery": "mystery_detective",
            "modern": "modern_analyst",
            "enterprise": "enterprise_ceo",
            "securities": "securities_trader",
            "military": "military_staff",
        }.get(seed, default_role)
        character = _write_character(seed, preferred, genre, seed=2000 + abs(hash(seed)) % 5000)

        outfit_entries = []
        prop_index: dict[str, str] = {}
        for i, o in enumerate(outfits):
            oid = o["id"]
            odir = civ_dir / "outfits" / oid
            odir.mkdir(parents=True, exist_ok=True)
            # also roles/{role_id}/
            rdir = civ_dir / "roles" / oid
            rdir.mkdir(parents=True, exist_ok=True)

            prop_paths = []
            for j, pname in enumerate(o["props"]):
                slug = _slug(pname)
                pdir = civ_dir / "props" / slug
                pdir.mkdir(parents=True, exist_ok=True)
                glb = pdir / "prop.glb"
                if not glb.is_file():
                    write_prop(glb, pname, seed=4000 + i * 17 + j)
                url = f"/models/characters/civilizations/{seed}/props/{slug}/prop.glb"
                prop_index[slug] = url
                prop_paths.append({"name": pname, "slug": slug, "glb": url})

            # clothing files as meta (no separate cloth glb — baked in body)
            entry = {
                **o,
                "props_assets": prop_paths,
                "body": f"/models/characters/roles/{oid}/body.glb",
                "clothing_note": "服饰轮廓已烘焙进 body.glb；下列为可选外观标签",
            }
            (odir / "meta.json").write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
            (rdir / "outfit.json").write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
            # symlink-like copy pointer to body
            (rdir / "body_url.txt").write_text(entry["body"], encoding="utf-8")
            outfit_entries.append({
                **entry,
                "meta_url": f"/models/characters/civilizations/{seed}/outfits/{oid}/meta.json",
            })
            print(f"outfit ok {seed}/{oid}")

        cat = {
            "id": seed,
            "name": meta_name,
            "genre": seed,
            "era": meta_name,
            "mesh_genre": genre,
            "character": character,
            "outfits": outfit_entries,
            "props": [{"slug": k, "glb": v} for k, v in sorted(prop_index.items())],
            "roles": [
                {
                    "id": e["id"],
                    "name": e["label"],
                    "body": e["body"],
                    "outfit_url": f"/models/characters/civilizations/{seed}/roles/{e['id']}/outfit.json",
                }
                for e in outfit_entries
            ],
        }
        (civ_dir / "catalog.json").write_text(json.dumps(cat, ensure_ascii=False, indent=2), encoding="utf-8")
        index.append({
            "id": seed,
            "name": meta_name,
            "era": meta_name,
            "outfit_count": len(outfit_entries),
            "prop_count": len(prop_index),
            "role_count": len(outfit_entries),
            "catalog_url": f"/models/characters/civilizations/{seed}/catalog.json",
            "character_url": character["body"],
        })

    (CIVS_DIR / "index.json").write_text(
        json.dumps({"civilizations": index}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    runtime = ROOT / "backend" / "data" / "runtime" / "generator" / "civilizations"
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / "index.json").write_text(
        json.dumps({"civilizations": index}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nDone. {len(index)} civs synced from player_catalog.")


if __name__ == "__main__":
    main()
