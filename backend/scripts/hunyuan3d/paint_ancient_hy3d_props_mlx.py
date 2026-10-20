#!/usr/bin/env python3
"""Paint 九州 character prop shape GLBs with Mac MLX Hunyuan Paint.

Inputs:
  frontend/.../props/{slug}/prop.glb  (shape; archived to prop_shape.glb)
  backend/data/runtime/generator/hy3d_char_props/{slug}/ref.png

Outputs:
  props/{slug}/prop.glb (textured) + painted.ok
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PAINT_PKG = ROOT / "third_party/Hunyuan3D-MLX/python/paint"
OUT_ROOT = ROOT / "frontend/public/models/characters/civilizations/ancient/props"
RUNTIME = ROOT / "backend/data/runtime/generator/hy3d_char_props"
READY = ROOT / "frontend/public/models/characters/civilizations/ancient/hy3d_props_ready.json"
WEIGHTS_CANDIDATES = [
    ROOT / "third_party/hy3d_mlx_weights/paint_rgb/hunyuan3d-paint-v2-0",
    ROOT / "third_party/hy3d_models/tencent/Hunyuan3D-2/hunyuan3d-paint-v2-0",
]

PROPS = [
    "笔墨纸砚", "案卷袋", "县衙腰牌", "朴刀", "铁胎弓", "狼牙箭_12",
    "袖中账", "通行路引", "钱袋", "线装书", "镖旗",
    # Clothing wardrobe pieces
    "青衫", "皮护腕", "皮围裙", "短褐背心", "麻短褐",
]
_MIN_BYTES = 50_000


def resolve_weights() -> Path:
    for p in WEIGHTS_CANDIDATES:
        if (p / "unet/diffusion_pytorch_model.safetensors").is_file() and (
            p / "vae/diffusion_pytorch_model.safetensors"
        ).is_file():
            return p
    raise SystemExit("Paint weights missing")


def ensure_weight_links(weights: Path) -> None:
    weights_root = PAINT_PKG / "weights"
    weights_root.mkdir(parents=True, exist_ok=True)
    link = weights_root / "hunyuan3d-paint-v2-0"
    if link.is_symlink() or link.is_file():
        link.unlink()
    elif link.exists():
        shutil.rmtree(link)
    link.symlink_to(weights.resolve())
    sr_dir = weights_root / "realesrgan"
    sr_dir.mkdir(parents=True, exist_ok=True)
    sr_src = ROOT / "third_party/hy3d_mlx_weights/paint/realesrgan/rrdbnet_mlx.safetensors"
    sr_dst = sr_dir / "rrdbnet_mlx.safetensors"
    if sr_src.is_file():
        if sr_dst.is_symlink() or sr_dst.is_file():
            sr_dst.unlink()
        elif sr_dst.exists():
            shutil.rmtree(sr_dst)
        sr_dst.symlink_to(sr_src.resolve())


def write_ready() -> None:
    ready = []
    painted = []
    for slug in PROPS:
        path = OUT_ROOT / slug / "prop.glb"
        ok = OUT_ROOT / slug / "painted.ok"
        if path.is_file() and path.stat().st_size > _MIN_BYTES:
            ready.append(slug)
            if ok.is_file():
                painted.append(slug)
    payload = {
        "engine": "hunyuan3d",
        "props": ready,
        "painted": painted,
        "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "min_bytes": _MIN_BYTES,
    }
    READY.parent.mkdir(parents=True, exist_ok=True)
    READY.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def paint_one(
    slug: str,
    *,
    weights: Path,
    res: int,
    tex: int,
    steps: int,
    sr: bool,
    force: bool,
    guid: float,
) -> None:
    mesh = OUT_ROOT / slug / "prop.glb"
    shape_bak = OUT_ROOT / slug / "prop_shape.glb"
    painted_ok = OUT_ROOT / slug / "painted.ok"
    ref = RUNTIME / slug / "ref.png"

    if not mesh.is_file() or mesh.stat().st_size < _MIN_BYTES:
        print(f"SKIP {slug}: no shape mesh"); return
    if not ref.is_file():
        print(f"SKIP {slug}: no ref.png"); return
    if painted_ok.is_file() and not force:
        print(f"SKIP {slug}: already painted"); return

    if not shape_bak.is_file():
        shutil.copy2(mesh, shape_bak)

    ensure_weight_links(weights)
    (PAINT_PKG / "outputs").mkdir(parents=True, exist_ok=True)
    work = ROOT / "backend/data/runtime/generator/hy3d_paint_mlx_props" / slug
    work.mkdir(parents=True, exist_ok=True)

    env = {
        **os.environ,
        "PAINT_MESH": str(shape_bak.resolve()),
        "PAINT_IMG": str(ref.resolve()),
        "PAINT_RES": str(res),
        "PAINT_TEX": str(tex),
        "PAINT_STEPS": str(steps),
        "PAINT_SR": "1" if sr else "0",
        "PAINT_GUID": str(guid),
        "PAINT_SCHED": "unipc",
    }
    print(f"== paint prop {slug} res={res} tex={tex} steps={steps} sr={sr} =="); sys.stdout.flush()
    t0 = time.time()
    py = ROOT / "backend/.venv-hunyuan3d/bin/python3"
    proc = subprocess.run(
        [str(py), "-u", str(PAINT_PKG / "scripts" / "run_paint.py")],
        cwd=str(PAINT_PKG),
        env=env,
        capture_output=False,
    )
    if proc.returncode != 0:
        raise SystemExit(f"paint failed for prop {slug} exit={proc.returncode}")
    produced = PAINT_PKG / "outputs" / "textured_mesh.glb"
    if not produced.is_file():
        raise SystemExit(f"paint produced no GLB for prop {slug}")
    shutil.copy2(produced, work / "textured_mesh.glb")
    for name in ("paint_texture.png", "paint_views.png", "textured_preview.png"):
        src = PAINT_PKG / "outputs" / name
        if src.is_file():
            shutil.copy2(src, work / name)
    shutil.copy2(produced, mesh)
    painted_ok.write_text(time.strftime("%Y-%m-%dT%H:%M:%S") + "\n", encoding="utf-8")
    write_ready()
    print(f"  ok {mesh} ({mesh.stat().st_size} bytes, {time.time()-t0:.0f}s)"); sys.stdout.flush()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--res", type=int, default=512)
    ap.add_argument("--tex", type=int, default=2048)
    ap.add_argument("--steps", type=int, default=20)
    ap.add_argument("--guid", type=float, default=2.75)
    ap.add_argument("--no-sr", action="store_true")
    ap.add_argument("--hq", action="store_true")
    args = ap.parse_args()
    if args.hq:
        args.res, args.tex, args.steps = 512, 2048, 20
        args.no_sr = False

    if not PAINT_PKG.is_dir():
        raise SystemExit(f"missing {PAINT_PKG}")
    weights = resolve_weights()
    print(f"weights={weights}"); sys.stdout.flush()

    want = {x.strip() for x in args.only.split(",") if x.strip()}
    slugs = [s for s in PROPS if not want or s in want]
    for slug in slugs:
        paint_one(
            slug,
            weights=weights,
            res=args.res,
            tex=args.tex,
            steps=args.steps,
            sr=not args.no_sr,
            force=args.force,
            guid=args.guid,
        )
    write_ready()
    print("all prop paint jobs finished")


if __name__ == "__main__":
    main()
