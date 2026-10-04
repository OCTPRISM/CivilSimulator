#!/usr/bin/env python3
"""Generate ancient street NPC bodies via lite ref → Hunyuan3D mesh.

Outputs:
  frontend/public/models/characters/roles/{role_id}/hy3d/body.glb

Usage:
  PYTHONPATH=backend backend/.venv/bin/python -u backend/scripts/generate_ancient_hy3d_npcs.py
  PYTHONPATH=backend backend/.venv/bin/python -u backend/scripts/generate_ancient_hy3d_npcs.py --only ancient_trader
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.generator import hunyuan_client  # noqa: E402
from app.generator.text_to_image_lite import render_reference_png  # noqa: E402
from app.config import get_settings  # noqa: E402

ROLES_ROOT = ROOT / "frontend/public/models/characters/roles"
READY = ROOT / "frontend/public/models/characters/hy3d_npc_ready.json"
RUNTIME = ROOT / "backend/data/runtime/generator/hy3d_npc"

NPCS: list[dict] = [
    {
        "id": "ancient_trader",
        "priority": 1,
        "prompt": (
            "full body Tang dynasty street merchant man, standing, front three-quarter view, "
            "red-brown robe with green sash, cloth shoes, topknot hair, game character asset, "
            "plain white background, no ground plane, complete body head to toe"
        ),
    },
    {
        "id": "ancient_student",
        "priority": 1,
        "prompt": (
            "full body Tang dynasty scholar student man, standing, indigo blue long robe, "
            "yellow sash, book under arm, topknot, front three-quarter, game character, "
            "white background, complete body"
        ),
    },
    {
        "id": "ancient_guard",
        "priority": 1,
        "prompt": (
            "full body Tang dynasty city guard man, standing, leather armor over brown tunic, "
            "red sash, boots, stern face, topknot, front three-quarter, game character, "
            "white background, complete body"
        ),
    },
    {
        "id": "ancient_clerk",
        "priority": 1,
        "prompt": (
            "full body Tang dynasty junior clerk official, standing, slate-blue robe, "
            "black gauze hat, belt plaque, front three-quarter, game character, "
            "white background, complete body"
        ),
    },
    {
        "id": "npc_drunkard",
        "priority": 2,
        "prompt": (
            "full body Tang dynasty farmer in rough hemp clothes, standing, straw sandals, "
            "simple hair, front three-quarter, game character, white background, complete body"
        ),
    },
    {
        "id": "npc_boatman",
        "priority": 2,
        "prompt": (
            "full body Tang dynasty boatman, standing, short jacket and trousers, "
            "bare forearms, headscarf, front three-quarter, game character, white background"
        ),
    },
]


def write_ready() -> None:
    ready = []
    for n in NPCS:
        p = ROLES_ROOT / n["id"] / "hy3d" / "body.glb"
        if p.is_file() and p.stat().st_size > 800:
            ready.append(n["id"])
    payload = {"engine": "hunyuan3d", "npcs": ready, "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%S")}
    READY.parent.mkdir(parents=True, exist_ok=True)
    READY.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def generate_one(npc: dict, *, force: bool) -> dict:
    out = ROLES_ROOT / npc["id"] / "hy3d" / "body.glb"
    if out.is_file() and out.stat().st_size > 800 and not force:
        return {"id": npc["id"], "status": "skip", "path": str(out.relative_to(ROOT))}

    status = hunyuan_client.check_status(timeout=5.0)
    if not status.get("online"):
        raise SystemExit(f"Hunyuan3D offline: {status.get('message')}")

    print(f"== {npc['id']} =="); sys.stdout.flush()
    t0 = time.time()
    print("  ref image (lite/character)…"); sys.stdout.flush()
    image_bytes = render_reference_png(npc["prompt"], kind="character")
    ref_path = RUNTIME / npc["id"] / "ref.png"
    ref_path.parent.mkdir(parents=True, exist_ok=True)
    ref_path.write_bytes(image_bytes)

    print("  hunyuan mesh…"); sys.stdout.flush()
    glb = hunyuan_client.generate_character_mesh(image_bytes, with_texture=False, timeout=3600.0)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(glb)
    shutil.copy2(out, RUNTIME / npc["id"] / "model.glb")
    meta = {
        "id": npc["id"],
        "bytes": len(glb),
        "seconds": round(time.time() - t0, 1),
        "engine": "hunyuan3d",
        "path": str(out.relative_to(ROOT)),
    }
    (RUNTIME / npc["id"] / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ok {out} ({len(glb)} bytes, {meta['seconds']}s)"); sys.stdout.flush()
    write_ready()
    return {"id": npc["id"], "status": "done", **meta}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--priority", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    want = {x.strip() for x in args.only.split(",") if x.strip()}
    npcs = NPCS
    if want:
        npcs = [n for n in NPCS if n["id"] in want]
    elif args.priority:
        npcs = [n for n in NPCS if n.get("priority", 9) == 1]

    print(f"plan {len(npcs)} NPC bodies → hy3d"); sys.stdout.flush()
    print(f"url={get_settings().hunyuan3d_url}"); sys.stdout.flush()
    write_ready()
    for npc in npcs:
        try:
            generate_one(npc, force=args.force)
        except Exception as exc:
            print(f"FAIL {npc['id']}: {exc}"); sys.stdout.flush()
            continue
    write_ready()
    print(f"ready {READY}"); sys.stdout.flush()


if __name__ == "__main__":
    main()
