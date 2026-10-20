#!/usr/bin/env python3
"""Paint existing 九州 hy3d shape GLBs with Mac MLX Hunyuan Paint (Python port).

Requires:
  - third_party/Hunyuan3D-MLX/python/paint (hy3dpaint_mlx)
  - weights at third_party/hy3d_mlx_weights/paint_rgb/hunyuan3d-paint-v2-0
    OR symlink from official tencent/Hunyuan3D-2/hunyuan3d-paint-v2-0
  - pip: mlx, xatlas, trimesh, pillow, numpy (in .venv-hunyuan3d)

Usage:
  backend/.venv-hunyuan3d/bin/python -u backend/scripts/hunyuan3d/paint_ancient_hy3d_mlx.py \\
    --only ancient_student --res 384 --tex 1024 --no-sr
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PAINT_PKG = ROOT / "third_party/Hunyuan3D-MLX/python/paint"
ROLES_ROOT = ROOT / "frontend/public/models/characters/roles"
RUNTIME = ROOT / "backend/data/runtime/generator/hy3d_npc"
WEIGHTS_CANDIDATES = [
    ROOT / "third_party/hy3d_mlx_weights/paint_rgb/hunyuan3d-paint-v2-0",
    ROOT / "third_party/hy3d_models/tencent/Hunyuan3D-2/hunyuan3d-paint-v2-0",
]

ROLES = [
    "ancient_student",
    "ancient_clerk",
    "ancient_guard",
    "ancient_archer",
    "ancient_trader",
    "ancient_farmer",
    "ancient_porter",
    "ancient_artisan",
]


def resolve_weights() -> Path:
    for p in WEIGHTS_CANDIDATES:
        if (p / "unet/diffusion_pytorch_model.safetensors").is_file() and (
            p / "vae/diffusion_pytorch_model.safetensors"
        ).is_file():
            return p
    raise SystemExit(
        "Paint weights missing. Download e.g.\n"
        "  hf download tencent/Hunyuan3D-2 --include 'hunyuan3d-paint-v2-0/**' "
        f"--local-dir {ROOT / 'third_party/hy3d_models/tencent/Hunyuan3D-2'}"
    )


def paint_one(
    rid: str,
    *,
    weights: Path,
    res: int,
    tex: int,
    steps: int,
    sr: bool,
    force: bool,
    guid: float = 2.75,
) -> None:
    mesh = ROLES_ROOT / rid / "hy3d" / "body.glb"
    shape_bak = ROLES_ROOT / rid / "hy3d" / "body_shape.glb"
    out_final = ROLES_ROOT / rid / "hy3d" / "body.glb"
    painted_ok = ROLES_ROOT / rid / "hy3d" / "painted.ok"
    ref = RUNTIME / rid / "ref.png"

    if not mesh.is_file():
        print(f"SKIP {rid}: no mesh"); return
    if not ref.is_file():
        print(f"SKIP {rid}: no ref.png"); return
    if painted_ok.is_file() and not force:
        print(f"SKIP {rid}: already painted"); return

    hy3d_dir = mesh.parent
    hy3d_dir.mkdir(parents=True, exist_ok=True)
    if not shape_bak.is_file():
        shutil.copy2(mesh, shape_bak)

    work = ROOT / "backend/data/runtime/generator/hy3d_paint_mlx" / rid
    work.mkdir(parents=True, exist_ok=True)
    # run_paint.py writes relative outputs/ under PAINT_PKG cwd — use a per-role work dir copy of script env
    out_dir = work / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Point package at our weights via symlink expected path inside paint pkg
    weights_root = PAINT_PKG / "weights"
    weights_root.mkdir(parents=True, exist_ok=True)
    weights_link = weights_root / "hunyuan3d-paint-v2-0"
    if weights_link.is_symlink() or weights_link.exists():
        if weights_link.is_symlink() or weights_link.is_file():
            weights_link.unlink()
        else:
            shutil.rmtree(weights_link)
    weights_link.symlink_to(weights.resolve())

    # RealESRGAN MLX weights (from hunyuan3d-mlx-paint-large bundle)
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
    # run_paint.py writes relative outputs/ under package cwd
    (PAINT_PKG / "outputs").mkdir(parents=True, exist_ok=True)
    print(f"== paint {rid} res={res} tex={tex} steps={steps} sr={sr} =="); sys.stdout.flush()
    t0 = time.time()
    py = ROOT / "backend/.venv-hunyuan3d/bin/python3"
    script = PAINT_PKG / "scripts" / "run_paint.py"
    proc = subprocess.run(
        [str(py), "-u", str(script)],
        cwd=str(PAINT_PKG),
        env=env,
        capture_output=False,
    )
    if proc.returncode != 0:
        raise SystemExit(f"paint failed for {rid} exit={proc.returncode}")

    produced = PAINT_PKG / "outputs" / "textured_mesh.glb"
    if not produced.is_file():
        raise SystemExit(f"paint produced no GLB for {rid}")
    # archive + promote
    shutil.copy2(produced, work / "textured_mesh.glb")
    for name in ("paint_texture.png", "paint_views.png", "textured_preview.png"):
        src = PAINT_PKG / "outputs" / name
        if src.is_file():
            shutil.copy2(src, work / name)
    shutil.copy2(produced, out_final)
    painted_ok.write_text(time.strftime("%Y-%m-%dT%H:%M:%S") + "\n", encoding="utf-8")
    print(f"  ok {out_final} ({out_final.stat().st_size} bytes, {time.time()-t0:.0f}s)"); sys.stdout.flush()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--res", type=int, default=512, help="multiview render res (HQ: 512)")
    ap.add_argument("--tex", type=int, default=2048, help="UV atlas size (HQ: 2048)")
    ap.add_argument("--steps", type=int, default=20, help="diffusion steps (HQ: 20)")
    ap.add_argument("--guid", type=float, default=2.75, help="CFG guidance")
    ap.add_argument("--no-sr", action="store_true", help="skip RealESRGAN (saves RAM)")
    ap.add_argument("--hq", action="store_true", help="alias: 512/2048/20 + SR")
    args = ap.parse_args()
    if args.hq:
        args.res, args.tex, args.steps = 512, 2048, 20
        args.no_sr = False

    if not PAINT_PKG.is_dir():
        raise SystemExit(f"missing {PAINT_PKG} — clone Hunyuan3D-MLX")

    weights = resolve_weights()
    print(f"weights={weights}"); sys.stdout.flush()

    want = {x.strip() for x in args.only.split(",") if x.strip()}
    roles = [r for r in ROLES if not want or r in want]
    for rid in roles:
        paint_one(
            rid,
            weights=weights,
            res=args.res,
            tex=args.tex,
            steps=args.steps,
            sr=not args.no_sr,
            force=args.force,
            guid=args.guid,
        )
    print("all paint jobs finished")


if __name__ == "__main__":
    main()
