#!/usr/bin/env python3
"""Generate ancient (九州) playable role bodies via DiT/lite ref → Hunyuan3D mesh.

Outputs:
  frontend/public/models/characters/roles/{role_id}/hy3d/body.glb

Usage:
  PYTHONPATH=backend backend/.venv/bin/python -u backend/scripts/generate_ancient_hy3d_npcs.py --force
  PYTHONPATH=backend backend/.venv/bin/python -u backend/scripts/generate_ancient_hy3d_npcs.py --only ancient_archer --force
  PYTHONPATH=backend backend/.venv/bin/python -u backend/scripts/generate_ancient_hy3d_npcs.py --priority --force --ref dit
"""
from __future__ import annotations

import argparse
import hashlib
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

# Identity FIRST (DiT CLI keeps ~160 chars of prompt). Shared quality suffix after.
_QUAL = (
    ", full-body head-to-toe standing, clear face eyes nose mouth, "
    "complete arms hands legs feet, volumetric Tang game character, "
    "front three-quarter, not bust not half-body, white background"
)

NPCS: list[dict] = [
    {
        "id": "ancient_student",
        "priority": 1,
        "prompt": (
            "寒门书生 indigo robe yellow sash book topknot youthful face "
            f"detailed eyes{_QUAL}"
        ),
    },
    {
        "id": "ancient_clerk",
        "priority": 1,
        "prompt": (
            "衙门小吏 slate robe black futou hat waist plaque satchel "
            f"middle-aged face{_QUAL}"
        ),
    },
    {
        "id": "ancient_guard",
        "priority": 1,
        "prompt": (
            "镖局趟子手 leather lamellar armor brown tunic red sash boots "
            f"stern face{_QUAL}"
        ),
    },
    {
        "id": "ancient_archer",
        "priority": 1,
        "prompt": (
            "边军斥候 dark-green padded armor cloak bow quiver boots "
            f"weathered face{_QUAL}"
        ),
    },
    {
        "id": "ancient_trader",
        "priority": 1,
        "prompt": (
            "西市行商 red-brown layered robe green sash account book "
            f"shrewd face{_QUAL}"
        ),
    },
    {
        "id": "ancient_farmer",
        "priority": 1,
        "prompt": (
            "田舍农夫 tall slim grey hemp tunic trousers straw hat "
            f"standing upright sunburned face{_QUAL}"
        ),
    },
    {
        "id": "ancient_porter",
        "priority": 1,
        "prompt": (
            "脚夫挑夫 brown vest trousers carrying pole shoulder yoke "
            f"muscular face{_QUAL}"
        ),
    },
    {
        "id": "ancient_artisan",
        "priority": 1,
        "prompt": (
            "匠作铁匠 black apron leather bracers hammer soot muscular "
            f"bearded face{_QUAL}"
        ),
    },
    {
        "id": "npc_drunkard",
        "priority": 2,
        "prompt": f"酒客 Tang drunkard loose robe flask weary face{_QUAL}",
    },
    {
        "id": "npc_boatman",
        "priority": 2,
        "prompt": f"船工 Tang boatman short jacket trousers headscarf{_QUAL}",
    },
]


def _prompt_hash(prompt: str) -> str:
    return hashlib.sha1(prompt.encode("utf-8")).hexdigest()[:12]


def _ref_image(prompt: str, *, mode: str) -> bytes:
    """Prefer HunyuanDiT when mode=dit; fall back to volumetric lite silhouette."""
    if mode == "dit":
        try:
            from app.generator.text_to_image import text_to_image_bytes
            return text_to_image_bytes(prompt, kind="character")
        except Exception as exc:
            print(f"  dit ref failed ({exc}); falling back to lite"); sys.stdout.flush()
    return render_reference_png(prompt, kind="character")


def write_ready(ids: list[str] | None = None) -> None:
    ready = []
    scan = ids or [n["id"] for n in NPCS]
    for rid in scan:
        p = ROLES_ROOT / rid / "hy3d" / "body.glb"
        if p.is_file() and p.stat().st_size > 400_000:
            ready.append(rid)
    # also keep any previously ready files not in scan
    if READY.is_file():
        try:
            prev = json.loads(READY.read_text(encoding="utf-8")).get("npcs") or []
            for rid in prev:
                if rid not in ready:
                    p = ROLES_ROOT / rid / "hy3d" / "body.glb"
                    if p.is_file() and p.stat().st_size > 400_000:
                        ready.append(rid)
        except Exception:
            pass
    payload = {
        "engine": "hunyuan3d",
        "npcs": sorted(set(ready)),
        "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "min_bytes": 400000,
    }
    READY.parent.mkdir(parents=True, exist_ok=True)
    READY.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def generate_one(npc: dict, *, force: bool, ref_mode: str) -> dict:
    out = ROLES_ROOT / npc["id"] / "hy3d" / "body.glb"
    if out.is_file() and out.stat().st_size > 400_000 and not force:
        return {"id": npc["id"], "status": "skip", "path": str(out.relative_to(ROOT)), "bytes": out.stat().st_size}

    status = hunyuan_client.check_status(timeout=5.0)
    if not status.get("online"):
        raise SystemExit(f"Hunyuan3D offline: {status.get('message')}")

    print(f"== {npc['id']} (ref={ref_mode}) =="); sys.stdout.flush()
    t0 = time.time()
    print("  ref image…"); sys.stdout.flush()
    image_bytes = _ref_image(npc["prompt"], mode=ref_mode)
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
        "ref_mode": ref_mode,
        "prompt_hash": _prompt_hash(npc["prompt"]),
        "path": str(out.relative_to(ROOT)),
        "gate_min_bytes": 400000,
        "gate_pass_size": len(glb) > 400_000,
    }
    (RUNTIME / npc["id"] / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    print(f"  ok {out} ({len(glb)} bytes, {meta['seconds']}s, size_gate={meta['gate_pass_size']})")
    sys.stdout.flush()
    write_ready()
    return {"id": npc["id"], "status": "done", **meta}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--priority", action="store_true", help="catalog playable roles only")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--ref", choices=("dit", "lite", "auto"), default="auto",
                    help="auto = use settings.hunyuan3d_text2img_mode")
    args = ap.parse_args()

    cfg = get_settings()
    if args.ref == "auto":
        ref_mode = "dit" if cfg.hunyuan3d_text2img_mode == "dit" else "lite"
    else:
        ref_mode = args.ref

    want = {x.strip() for x in args.only.split(",") if x.strip()}
    npcs = NPCS
    if want:
        npcs = [n for n in NPCS if n["id"] in want]
        missing = want - {n["id"] for n in npcs}
        if missing:
            raise SystemExit(f"unknown ids: {sorted(missing)}")
    elif args.priority:
        npcs = [n for n in NPCS if n.get("priority", 9) == 1]

    print(f"plan {len(npcs)} NPC bodies → hy3d ref={ref_mode}"); sys.stdout.flush()
    print(f"url={cfg.hunyuan3d_url} texture={cfg.hunyuan3d_texture}"); sys.stdout.flush()
    write_ready()
    results = []
    for npc in npcs:
        try:
            results.append(generate_one(npc, force=args.force, ref_mode=ref_mode))
        except SystemExit:
            raise
        except Exception as exc:
            print(f"FAIL {npc['id']}: {exc}"); sys.stdout.flush()
            results.append({"id": npc["id"], "status": "fail", "error": str(exc)})
            continue
    write_ready([n["id"] for n in npcs])
    ready = json.loads(READY.read_text(encoding="utf-8")) if READY.is_file() else {}
    print(f"ready {READY} → {ready.get('npcs')}"); sys.stdout.flush()
    failed = [r["id"] for r in results if r.get("status") == "fail"]
    if failed:
        print(f"FAILED: {failed}"); sys.stdout.flush()
        sys.exit(1)


if __name__ == "__main__":
    main()
