#!/usr/bin/env python3
"""Paint per-role outfit body variants (full mesh swap — never layered overlays).

Same hy3d shape as the role; reference biased toward a clothing style.
Outputs:
  frontend/.../roles/{role}/hy3d/outfits/{outfit}/body.glb
  frontend/public/models/characters/hy3d_outfit_ready.json
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

from PIL import Image, ImageEnhance, ImageOps

ROOT = Path(__file__).resolve().parents[3]
PAINT_PKG = ROOT / "third_party/Hunyuan3D-MLX/python/paint"
ROLES_ROOT = ROOT / "frontend/public/models/characters/roles"
ROLE_RUNTIME = ROOT / "backend/data/runtime/generator/hy3d_npc"
CLOTH_RUNTIME = ROOT / "backend/data/runtime/generator/hy3d_char_props"
READY = ROOT / "frontend/public/models/characters/hy3d_outfit_ready.json"
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
# Full-garment styles — each becomes a complete body.glb for mesh swap.
OUTFITS = ("青衫", "麻短褐", "短褐背心", "皮围裙", "皮护腕")

# Mild color bias so Paint prefers that garment family on the shared shape.
OUTFIT_TINT: dict[str, tuple[float, float, float, float]] = {
    "青衫": (0.72, 0.88, 1.18, 1.02),
    "麻短褐": (1.08, 0.92, 0.72, 0.96),
    "短褐背心": (1.05, 0.9, 0.75, 0.98),
    "皮围裙": (0.85, 0.78, 0.7, 0.94),
    "皮护腕": (0.95, 0.85, 0.75, 1.0),
}


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


def build_outfit_ref(role_ref: Path, cloth_ref: Path | None, outfit: str, dst: Path) -> None:
    """Role identity as base; clothing product shot guides fabric/color on the side."""
    import numpy as np

    base = Image.open(role_ref).convert("RGB")
    size = 768
    base = ImageOps.fit(base, (size, size), method=Image.Resampling.LANCZOS)
    r_m, g_m, b_m, bright = OUTFIT_TINT.get(outfit, (1.0, 1.0, 1.0, 1.0))
    arr = np.asarray(base, dtype=np.float32)
    # Bias mid-body band (rough torso) toward outfit tint — keeps face/identity.
    y0, y1 = int(size * 0.28), int(size * 0.78)
    band = arr[y0:y1].copy()
    band[..., 0] *= r_m
    band[..., 1] *= g_m
    band[..., 2] *= b_m
    arr[y0:y1] = band
    out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode="RGB")
    out = ImageEnhance.Brightness(out).enhance(bright)
    if cloth_ref and cloth_ref.is_file():
        cloth = Image.open(cloth_ref).convert("RGB")
        cloth = ImageOps.fit(cloth, (size // 3, size // 3), method=Image.Resampling.LANCZOS)
        # Corner inset: garment cue for Paint without replacing the person.
        out.paste(cloth, (size - cloth.width - 12, 12))
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.save(dst, format="PNG")


def write_ready() -> None:
    outfits: dict[str, list[str]] = {}
    for rid in ROLES:
        done = []
        for outfit in OUTFITS:
            path = ROLES_ROOT / rid / "hy3d" / "outfits" / outfit / "body.glb"
            ok = ROLES_ROOT / rid / "hy3d" / "outfits" / outfit / "painted.ok"
            if path.is_file() and path.stat().st_size > 400_000 and ok.is_file():
                done.append(outfit)
        if done:
            outfits[rid] = done
    payload = {
        "engine": "hunyuan3d-paint-mlx",
        "outfits": outfits,
        "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    READY.parent.mkdir(parents=True, exist_ok=True)
    READY.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def paint_one(
    rid: str,
    outfit: str,
    *,
    weights: Path,
    res: int,
    tex: int,
    steps: int,
    sr: bool,
    force: bool,
    guid: float,
) -> None:
    shape = ROLES_ROOT / rid / "hy3d" / "body_shape.glb"
    if not shape.is_file():
        shape = ROLES_ROOT / rid / "hy3d" / "body.glb"
    role_ref = ROLE_RUNTIME / rid / "ref.png"
    cloth_ref = CLOTH_RUNTIME / outfit / "ref.png"
    out_dir = ROLES_ROOT / rid / "hy3d" / "outfits" / outfit
    out_final = out_dir / "body.glb"
    painted_ok = out_dir / "painted.ok"

    if not shape.is_file():
        print(f"SKIP {rid}/{outfit}: no shape"); return
    if not role_ref.is_file():
        print(f"SKIP {rid}/{outfit}: no role ref"); return
    if painted_ok.is_file() and out_final.is_file() and not force:
        print(f"SKIP {rid}/{outfit}: already painted"); return

    work = ROOT / "backend/data/runtime/generator/hy3d_paint_mlx_outfits" / rid / outfit
    work.mkdir(parents=True, exist_ok=True)
    graded = work / "ref_outfit.png"
    build_outfit_ref(role_ref, cloth_ref if cloth_ref.is_file() else None, outfit, graded)

    ensure_weight_links(weights)
    (PAINT_PKG / "outputs").mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    env = {
        **os.environ,
        "PAINT_MESH": str(shape.resolve()),
        "PAINT_IMG": str(graded.resolve()),
        "PAINT_RES": str(res),
        "PAINT_TEX": str(tex),
        "PAINT_STEPS": str(steps),
        "PAINT_SR": "1" if sr else "0",
        "PAINT_GUID": str(guid),
        "PAINT_SCHED": "unipc",
    }
    print(f"== paint outfit {rid}/{outfit} res={res} tex={tex} steps={steps} sr={sr} =="); sys.stdout.flush()
    t0 = time.time()
    py = ROOT / "backend/.venv-hunyuan3d/bin/python3"
    proc = subprocess.run(
        [str(py), "-u", str(PAINT_PKG / "scripts" / "run_paint.py")],
        cwd=str(PAINT_PKG),
        env=env,
        capture_output=False,
    )
    if proc.returncode != 0:
        raise SystemExit(f"paint failed for {rid}/{outfit} exit={proc.returncode}")
    produced = PAINT_PKG / "outputs" / "textured_mesh.glb"
    if not produced.is_file():
        raise SystemExit(f"paint produced no GLB for {rid}/{outfit}")
    shutil.copy2(produced, work / "textured_mesh.glb")
    for name in ("paint_texture.png", "paint_views.png", "textured_preview.png"):
        src = PAINT_PKG / "outputs" / name
        if src.is_file():
            shutil.copy2(src, work / name)
    shutil.copy2(produced, out_final)
    painted_ok.write_text(time.strftime("%Y-%m-%dT%H:%M:%S") + "\n", encoding="utf-8")
    write_ready()
    print(f"  ok {out_final} ({out_final.stat().st_size} bytes, {time.time()-t0:.0f}s)"); sys.stdout.flush()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="role ids comma-separated")
    ap.add_argument("--outfits", default="", help="outfit slugs comma-separated")
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

    want_roles = {x.strip() for x in args.only.split(",") if x.strip()}
    want_outfits = {x.strip() for x in args.outfits.split(",") if x.strip()}
    roles = [r for r in ROLES if not want_roles or r in want_roles]
    outfits = [o for o in OUTFITS if not want_outfits or o in want_outfits]

    if not PAINT_PKG.is_dir():
        raise SystemExit(f"missing {PAINT_PKG}")
    weights = resolve_weights()
    print(f"weights={weights} roles={len(roles)} outfits={len(outfits)}"); sys.stdout.flush()

    for rid in roles:
        for outfit in outfits:
            paint_one(
                rid,
                outfit,
                weights=weights,
                res=args.res,
                tex=args.tex,
                steps=args.steps,
                sr=not args.no_sr,
                force=args.force,
                guid=args.guid,
            )
    write_ready()
    print(f"all outfit paint jobs finished → {READY}")


if __name__ == "__main__":
    main()
