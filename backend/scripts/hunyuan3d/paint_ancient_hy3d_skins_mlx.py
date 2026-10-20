#!/usr/bin/env python3
"""Paint per-skin hy3d body variants from the same shape + tone-graded refs.

Outputs:
  frontend/.../roles/{role}/hy3d/skins/{fair|tan|warm|pale}/body.glb
  frontend/public/models/characters/hy3d_skin_ready.json
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

from PIL import Image, ImageEnhance

ROOT = Path(__file__).resolve().parents[3]
PAINT_PKG = ROOT / "third_party/Hunyuan3D-MLX/python/paint"
ROLES_ROOT = ROOT / "frontend/public/models/characters/roles"
RUNTIME = ROOT / "backend/data/runtime/generator/hy3d_npc"
READY = ROOT / "frontend/public/models/characters/hy3d_skin_ready.json"
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
SKINS = ("fair", "tan", "warm", "pale")

# RGB multiply + brightness for DiT ref → skin-tone bias before Paint.
SKIN_GRADE: dict[str, tuple[float, float, float, float]] = {
    "fair": (1.12, 1.06, 1.02, 1.08),
    "pale": (1.08, 1.08, 1.14, 1.1),
    "warm": (1.14, 0.98, 0.88, 1.02),
    "tan": (0.88, 0.78, 0.66, 0.92),
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


def grade_ref(src: Path, dst: Path, skin: str) -> None:
    import numpy as np

    r_m, g_m, b_m, bright = SKIN_GRADE[skin]
    im = Image.open(src).convert("RGB")
    arr = np.asarray(im, dtype=np.float32)
    arr[..., 0] *= r_m
    arr[..., 1] *= g_m
    arr[..., 2] *= b_m
    im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode="RGB")
    im = ImageEnhance.Brightness(im).enhance(bright)
    dst.parent.mkdir(parents=True, exist_ok=True)
    im.save(dst, format="PNG")


def write_ready() -> None:
    skins: dict[str, list[str]] = {}
    for rid in ROLES:
        done = []
        for skin in SKINS:
            path = ROLES_ROOT / rid / "hy3d" / "skins" / skin / "body.glb"
            ok = ROLES_ROOT / rid / "hy3d" / "skins" / skin / "painted.ok"
            if path.is_file() and path.stat().st_size > 400_000 and ok.is_file():
                done.append(skin)
        if done:
            skins[rid] = done
    payload = {
        "engine": "hunyuan3d-paint-mlx",
        "skins": skins,
        "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    READY.parent.mkdir(parents=True, exist_ok=True)
    READY.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def seed_default_from_body(rid: str, skin: str) -> None:
    """Promote current painted body as one selectable skin so UI works immediately."""
    src = ROLES_ROOT / rid / "hy3d" / "body.glb"
    out_dir = ROLES_ROOT / rid / "hy3d" / "skins" / skin
    out = out_dir / "body.glb"
    ok = out_dir / "painted.ok"
    if not src.is_file() or src.stat().st_size < 400_000:
        return
    if out.is_file() and ok.is_file():
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, out)
    ok.write_text(time.strftime("%Y-%m-%dT%H:%M:%S") + " seeded\n", encoding="utf-8")
    print(f"  seeded {rid}/{skin} from body.glb ({out.stat().st_size} bytes)")


def paint_one(
    rid: str,
    skin: str,
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
    base_ref = RUNTIME / rid / "ref.png"
    out_dir = ROLES_ROOT / rid / "hy3d" / "skins" / skin
    out_final = out_dir / "body.glb"
    painted_ok = out_dir / "painted.ok"

    if not shape.is_file():
        print(f"SKIP {rid}/{skin}: no shape"); return
    if not base_ref.is_file():
        print(f"SKIP {rid}/{skin}: no ref.png"); return
    if painted_ok.is_file() and not force:
        text = painted_ok.read_text(encoding="utf-8")
        # Re-paint seeded placeholders; skip true Paint outputs.
        if "seeded" not in text:
            print(f"SKIP {rid}/{skin}: already painted"); return

    work = ROOT / "backend/data/runtime/generator/hy3d_paint_mlx_skins" / rid / skin
    work.mkdir(parents=True, exist_ok=True)
    graded = work / "ref_graded.png"
    grade_ref(base_ref, graded, skin)

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
    print(f"== paint skin {rid}/{skin} res={res} tex={tex} steps={steps} sr={sr} =="); sys.stdout.flush()
    t0 = time.time()
    py = ROOT / "backend/.venv-hunyuan3d/bin/python3"
    proc = subprocess.run(
        [str(py), "-u", str(PAINT_PKG / "scripts" / "run_paint.py")],
        cwd=str(PAINT_PKG),
        env=env,
        capture_output=False,
    )
    if proc.returncode != 0:
        raise SystemExit(f"paint failed for {rid}/{skin} exit={proc.returncode}")
    produced = PAINT_PKG / "outputs" / "textured_mesh.glb"
    if not produced.is_file():
        raise SystemExit(f"paint produced no GLB for {rid}/{skin}")
    shutil.copy2(produced, work / "textured_mesh.glb")
    for name in ("paint_texture.png", "paint_views.png", "textured_preview.png"):
        src = PAINT_PKG / "outputs" / name
        if src.is_file():
            shutil.copy2(src, work / name)
    shutil.copy2(produced, out_final)
    painted_ok.write_text(time.strftime("%Y-%m-%dT%H:%M:%S") + "\n", encoding="utf-8")
    # Keep default body in sync with this role's primary skin if matching.
    write_ready()
    print(f"  ok {out_final} ({out_final.stat().st_size} bytes, {time.time()-t0:.0f}s)"); sys.stdout.flush()


# Default skin to seed from current body (matches FIGURE_PRESETS tone).
DEFAULT_SKIN = {
    "ancient_student": "pale",
    "ancient_clerk": "fair",
    "ancient_guard": "warm",
    "ancient_archer": "tan",
    "ancient_trader": "tan",
    "ancient_farmer": "tan",
    "ancient_porter": "warm",
    "ancient_artisan": "tan",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="role ids comma-separated")
    ap.add_argument("--skins", default="", help="skin ids comma-separated")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--seed-only", action="store_true", help="only seed default skins from body.glb")
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
    want_skins = {x.strip() for x in args.skins.split(",") if x.strip()}
    roles = [r for r in ROLES if not want_roles or r in want_roles]
    skins = [s for s in SKINS if not want_skins or s in want_skins]

    print("seeding default skins from current painted bodies…"); sys.stdout.flush()
    for rid in roles:
        seed_default_from_body(rid, DEFAULT_SKIN.get(rid, "fair"))
    write_ready()
    if args.seed_only:
        print(f"ready {READY}"); return

    if not PAINT_PKG.is_dir():
        raise SystemExit(f"missing {PAINT_PKG}")
    weights = resolve_weights()
    print(f"weights={weights}"); sys.stdout.flush()

    for rid in roles:
        for skin in skins:
            paint_one(
                rid,
                skin,
                weights=weights,
                res=args.res,
                tex=args.tex,
                steps=args.steps,
                sr=not args.no_sr,
                force=args.force,
                guid=args.guid,
            )
    write_ready()
    print("all skin paint jobs finished")


if __name__ == "__main__":
    main()
