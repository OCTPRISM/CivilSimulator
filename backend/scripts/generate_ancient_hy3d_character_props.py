#!/usr/bin/env python3
"""Hunyuan3D re-render for 九州 catalog character props (not map props).

Outputs:
  frontend/public/models/characters/civilizations/ancient/props/{slug}/prop.glb

Usage:
  PYTHONPATH=backend backend/.venv/bin/python -u backend/scripts/generate_ancient_hy3d_character_props.py --force
  PYTHONPATH=backend backend/.venv/bin/python -u backend/scripts/generate_ancient_hy3d_character_props.py --only 朴刀 --force
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

OUT_ROOT = ROOT / "frontend/public/models/characters/civilizations/ancient/props"
RUNTIME = ROOT / "backend/data/runtime/generator/hy3d_char_props"
READY = ROOT / "frontend/public/models/characters/civilizations/ancient/hy3d_props_ready.json"

# Identity FIRST — DiT CLI truncates to ~160 chars; shared quality suffix after.
_QUAL = (
    ", Tang dynasty game prop, solid volumetric 3D object, not flat paper, "
    "centered product shot, white background, no hands, no people"
)

PROPS: list[dict] = [
    {
        "slug": "笔墨纸砚",
        "seed": 101,
        "prompt": f"笔墨纸砚 Chinese calligraphy set inkstone brush inkstick paper stack{_QUAL}",
    },
    {
        "slug": "案卷袋",
        "seed": 102,
        "prompt": f"案卷袋 leather document satchel strap rolled scrolls{_QUAL}",
    },
    {
        "slug": "县衙腰牌",
        "seed": 103,
        "prompt": f"县衙腰牌 bronze yamen waist plaque cord engraved seal{_QUAL}",
    },
    {
        "slug": "朴刀",
        "seed": 104,
        "prompt": f"朴刀 Tang pu dao saber wooden scabbard full blade{_QUAL}",
    },
    {
        "slug": "铁胎弓",
        "seed": 105,
        "prompt": f"铁胎弓 composite reflex bow wood horn limbs unstrung{_QUAL}",
    },
    {
        "slug": "狼牙箭_12",
        "seed": 106,
        "prompt": f"狼牙箭 quiver twelve wolf-tooth arrows fletched shafts{_QUAL}",
    },
    {
        "slug": "袖中账",
        "seed": 107,
        "prompt": f"袖中账 small bound account booklet string binding{_QUAL}",
    },
    {
        "slug": "通行路引",
        "seed": 108,
        "prompt": f"通行路引 Tang travel pass scroll official seal ribbon{_QUAL}",
    },
    {
        "slug": "钱袋",
        "seed": 109,
        "prompt": f"钱袋 Tang cloth coin pouch drawstring{_QUAL}",
    },
    {
        "slug": "线装书",
        "seed": 110,
        "prompt": f"线装书 stitched thread-bound Chinese book{_QUAL}",
    },
    {
        "slug": "镖旗",
        "seed": 111,
        "prompt": f"镖旗 escort agency banner flag on short pole{_QUAL}",
    },
    # Wearable clothing overlays — separate meshes, user-toggleable on the figure
    {
        "slug": "青衫",
        "seed": 201,
        "prompt": (
            f"青衫 Tang scholar cyan-blue long robe hanfu folded collar "
            f"sleeves hanging empty garment no mannequin no person{_QUAL}"
        ),
    },
    {
        "slug": "皮护腕",
        "seed": 202,
        "prompt": (
            f"皮护腕 pair Tang leather bracers wristguards brown straps "
            f"product shot empty armor piece no hands{_QUAL}"
        ),
    },
    {
        "slug": "皮围裙",
        "seed": 203,
        "prompt": (
            f"皮围裙 thick blacksmith leather apron straps pockets "
            f"hanging empty garment no person{_QUAL}"
        ),
    },
    {
        "slug": "短褐背心",
        "seed": 204,
        "prompt": (
            f"短褐背心 coarse hemp sleeveless vest short brown tunic "
            f"empty garment product shot no person{_QUAL}"
        ),
    },
    {
        "slug": "麻短褐",
        "seed": 205,
        "prompt": (
            f"麻短褐 coarse hemp short farmer tunic brown cloth "
            f"empty garment product shot no person{_QUAL}"
        ),
    },
]

# Prop meshes from Hunyuan should be well above placeholder kilobyte stubs.
_MIN_PROP_BYTES = 50_000


def _ref_image(prompt: str, *, mode: str, seed: int) -> bytes:
    if mode == "dit":
        try:
            from app.generator.text_to_image import text_to_image_bytes
            return text_to_image_bytes(prompt, kind="prop", seed=seed)
        except Exception as exc:
            print(f"  dit ref failed ({exc}); lite fallback"); sys.stdout.flush()
    return render_reference_png(prompt, kind="prop")


def write_ready() -> None:
    ready = []
    for p in PROPS:
        path = OUT_ROOT / p["slug"] / "prop.glb"
        if path.is_file() and path.stat().st_size > _MIN_PROP_BYTES:
            ready.append(p["slug"])
    payload = {
        "engine": "hunyuan3d",
        "props": ready,
        "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "min_bytes": _MIN_PROP_BYTES,
    }
    READY.parent.mkdir(parents=True, exist_ok=True)
    READY.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def generate_one(prop: dict, *, force: bool, ref_mode: str) -> dict:
    out = OUT_ROOT / prop["slug"] / "prop.glb"
    if out.is_file() and out.stat().st_size > _MIN_PROP_BYTES and not force:
        return {"slug": prop["slug"], "status": "skip", "bytes": out.stat().st_size}

    status = hunyuan_client.check_status(timeout=5.0)
    if not status.get("online"):
        raise SystemExit(f"Hunyuan3D offline: {status.get('message')}")

    print(f"== prop {prop['slug']} (ref={ref_mode}) =="); sys.stdout.flush()
    t0 = time.time()
    image_bytes = _ref_image(prop["prompt"], mode=ref_mode, seed=int(prop.get("seed", 42)))
    run = RUNTIME / prop["slug"]
    run.mkdir(parents=True, exist_ok=True)
    (run / "ref.png").write_bytes(image_bytes)

    glb = hunyuan_client.generate_mesh(image_bytes, with_texture=False, timeout=3600.0)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(glb)
    shutil.copy2(out, run / "model.glb")
    meta = {
        "slug": prop["slug"],
        "bytes": len(glb),
        "seconds": round(time.time() - t0, 1),
        "engine": "hunyuan3d",
        "ref_mode": ref_mode,
        "seed": prop.get("seed"),
        "prompt_hash": __import__("hashlib").sha256(prop["prompt"].encode()).hexdigest()[:16],
        "path": str(out.relative_to(ROOT)),
    }
    (run / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"  ok {out} ({len(glb)} bytes, {meta['seconds']}s)"); sys.stdout.flush()
    write_ready()
    return {"status": "done", **meta}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--ref", choices=("dit", "lite", "auto"), default="lite",
                    help="default lite for props (faster); dit for max quality")
    args = ap.parse_args()

    cfg = get_settings()
    if args.ref == "auto":
        ref_mode = "dit" if cfg.hunyuan3d_text2img_mode == "dit" else "lite"
    else:
        ref_mode = args.ref

    want = {x.strip() for x in args.only.split(",") if x.strip()}
    props = PROPS
    if want:
        props = [p for p in PROPS if p["slug"] in want]
        missing = want - {p["slug"] for p in props}
        if missing:
            raise SystemExit(f"unknown slugs: {sorted(missing)}")

    print(f"plan {len(props)} character props → hy3d ref={ref_mode}"); sys.stdout.flush()
    write_ready()
    for prop in props:
        try:
            generate_one(prop, force=args.force, ref_mode=ref_mode)
        except SystemExit:
            raise
        except Exception as exc:
            print(f"FAIL {prop['slug']}: {exc}"); sys.stdout.flush()
            continue
    write_ready()
    print(f"ready {READY}"); sys.stdout.flush()


if __name__ == "__main__":
    main()
