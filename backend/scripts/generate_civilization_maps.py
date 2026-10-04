#!/usr/bin/env python3
"""Generate distinct per-civilization maps (layout JSON + HunyuanDiT / procedural PNG).

Outputs:
  frontend/public/maps/{civ}.json   — World3D layout (unique terrain/cities)
  frontend/public/maps/{civ}.png    — painted overview (DiT when available)
  frontend/public/models/characters/civilizations/{civ}/map/  — mirror + brief

Usage:
  python3 backend/scripts/generate_civilization_maps.py
  python3 backend/scripts/generate_civilization_maps.py --dit   # use HunyuanDiT paint
  python3 backend/scripts/generate_civilization_maps.py --civ wuxia --dit
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "backend" / "scripts"))

from app.generator.civilization_maps import MAP_DNA, list_map_briefs, map_brief, paint_style_for  # noqa: E402
from layout_city_maps import GENRE_META, build_genre  # noqa: E402

OUT_MAPS = ROOT / "frontend" / "public" / "maps"
CIV_ROOT = ROOT / "frontend" / "public" / "models" / "characters" / "civilizations"
RUNTIME = ROOT / "backend" / "data" / "runtime" / "generator" / "maps"
W, H = 960, 540
VENV_PY = ROOT / "backend" / ".venv-hunyuan3d" / "bin" / "python3"
T2I_CLI = ROOT / "backend" / "scripts" / "hunyuan3d" / "text_to_image_cli.py"


def _height_field(shape: str, seed: int, scale: float) -> np.ndarray:
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    nx, ny = x / W, y / H
    base = (
        np.sin(nx * (4.5 + scale) + seed * 0.01) * 0.10 * scale
        + np.cos(ny * (3.8 + scale * 0.5)) * 0.09 * scale
        + rng.random((H, W), dtype=np.float32) * 0.06
    )
    if shape == "rivers_and_peaks":
        base += np.exp(-((nx - 0.28) ** 2 + (ny - 0.42) ** 2) * 14) * 0.42
        base += np.exp(-((nx - 0.75) ** 2 + (ny - 0.35) ** 2) * 10) * 0.35
        base -= np.exp(-((ny - 0.55) ** 2) * 40) * 0.12  # river trench
    elif shape == "floating_isles":
        base = np.maximum(base * 0.5, np.exp(-((nx - 0.5) ** 2 + (ny - 0.35) ** 2) * 6) * 0.65)
        base += np.exp(-((nx - 0.78) ** 2 + (ny - 0.18) ** 2) * 20) * 0.4
    elif shape == "river_plains":
        base *= 0.55
        base += np.exp(-((ny - 0.72) ** 2) * 30) * -0.08
        base += np.exp(-((nx - 0.5) ** 2 + (ny - 0.22) ** 2) * 18) * 0.18  # palace rise
    elif shape == "fog_harbor":
        base *= 0.45
        base[:, int(W * 0.3):] *= 0.85
        base[int(H * 0.7):, :] *= 0.3  # sea
    elif shape == "city_grid":
        base *= 0.35 + 0.1 * scale
    elif shape == "orbital_hub":
        rr = np.sqrt((nx - 0.5) ** 2 + (ny - 0.48) ** 2)
        base = 0.25 + 0.35 * np.exp(-((rr - 0.22) ** 2) * 40) + 0.2 * np.exp(-(rr ** 2) * 8)
    elif shape == "campus_plateau":
        base = 0.35 + 0.08 * np.sin(nx * 12) * np.cos(ny * 10)
        base = np.clip(base, 0.25, 0.55)
    elif shape == "lake_finance":
        base *= 0.3
        base += 0.15 * np.exp(-((nx - 0.5) ** 2 + (ny - 0.55) ** 2) * 6)
        lake = np.exp(-((nx - 0.5) ** 2 / 0.12 + (ny - 0.65) ** 2 / 0.05))
        base = base * (1 - 0.7 * lake)
    elif shape == "canyon_front":
        base += np.exp(-((nx - 0.35) ** 2) * 8) * 0.5
        base += np.exp(-((nx - 0.72) ** 2 + (ny - 0.55) ** 2) * 10) * 0.4
        base -= np.exp(-(((nx - 0.55) / 0.08) ** 2 + ((ny - 0.5) / 0.35) ** 2)) * 0.2
    return np.clip(base, 0, 1)


def paint_procedural(civ: str, layout: dict) -> Image.Image:
    brief = map_brief(civ)
    dna = brief["dna"]
    st = paint_style_for(civ)
    seed = int(layout.get("terrain", {}).get("seed") or 1000)
    hf = _height_field(dna["shape"], seed, float(dna["world_scale"]))
    water_cut = 0.18 + max(0, -float(dna["water_level"])) * 0.15
    px = np.zeros((H, W, 3), dtype=np.uint8)
    for yi in range(H):
        for xi in range(W):
            h = float(hf[yi, xi])
            if h < water_cut:
                px[yi, xi] = st["water"]
            else:
                t = (h - water_cut) / max(1e-6, 1 - water_cut)
                px[yi, xi] = tuple(
                    int(st["land_low"][c] * (1 - t) + st["land_hi"][c] * t) for c in range(3)
                )
    img = Image.fromarray(px, "RGB")
    veg_n = {
        "ancient": 520, "wuxia": 920, "xuanhuan": 360, "mystery": 180,
        "modern": 420, "scifi": 70, "enterprise": 460, "securities": 260, "military": 200,
    }.get(civ, 300)
    rng = np.random.default_rng(seed + 7)
    draw = ImageDraw.Draw(img)
    for _ in range(veg_n):
        x = int(rng.integers(0, W))
        y = int(rng.integers(0, H))
        if float(hf[y, x]) < water_cut + 0.05:
            continue
        col = st["land_hi"]
        if civ == "xuanhuan":
            col = (90, 50, 140)
        elif civ == "military":
            col = (90, 100, 70)
        elif civ == "scifi":
            col = (40, 120, 130)
        elif civ == "enterprise":
            col = (80, 160, 120)
        r = 1 if veg_n > 600 else 2
        draw.ellipse((x - r, y - r, x + r, y + r), fill=col)

    # roads from layout
    for road in layout.get("roads") or []:
        a, b = road.get("from"), road.get("to")
        if not a or not b:
            continue
        draw.line((a[0], a[1], b[0], b[1]), fill=st["road"], width=st["road_width"])

    for loc in layout.get("locations") or []:
        lx, ly = int(loc["x"]), int(loc["y"])
        draw.ellipse((lx - 7, ly - 7, lx + 7, ly + 7), fill=st["accent"], outline=st["label"])
        name = str(loc.get("name") or "")[:10]
        draw.text((lx + 9, ly - 7), name, fill=st["label"])

    # title strip
    draw.rectangle((0, 0, W, 28), fill=tuple(max(0, c - 20) for c in st["sky"]))
    title = f"{brief['name']}  ·  scale {dna['world_scale']}  ·  {dna['vegetation']}"
    draw.text((12, 7), title[:80], fill=st["label"])
    return img.filter(ImageFilter.GaussianBlur(radius=0.35))


def paint_dit(civ: str, out_path: Path) -> bool:
    if not VENV_PY.is_file() or not T2I_CLI.is_file():
        print(f"  dit skip {civ}: hunyuan venv/cli missing", flush=True)
        return False
    brief = map_brief(civ)
    tmp = out_path.with_suffix(".dit.png")
    cmd = [
        str(VENV_PY), "-u", str(T2I_CLI),
        brief["dit_prompt"][:200],
        "-o", str(tmp),
        "--device", "cpu",
        "--seed", str(1000 + abs(hash(civ)) % 9000),
        "--kind", "map",
        "--steps", "12",
        "--size", "768",
    ]
    env = {
        **dict(**{k: v for k, v in __import__("os").environ.items()}),
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "PYTHONUNBUFFERED": "1",
    }
    print(f"  dit paint {civ} …", flush=True)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600, env=env)
    except Exception as exc:
        print(f"  dit fail {civ}: {exc}", flush=True)
        return False
    if proc.returncode != 0 or not tmp.is_file():
        print(f"  dit fail {civ}: {(proc.stderr or proc.stdout)[:400]}", flush=True)
        return False
    img = Image.open(tmp).convert("RGB").resize((W, H), Image.Resampling.LANCZOS)
    img.save(out_path, "PNG")
    tmp.unlink(missing_ok=True)
    print(f"  dit ok {civ}", flush=True)
    return True


def generate_one(civ: str, *, use_dit: bool) -> dict:
    OUT_MAPS.mkdir(parents=True, exist_ok=True)
    RUNTIME.mkdir(parents=True, exist_ok=True)
    brief = map_brief(civ)
    layout = build_genre(civ)
    # stamp DNA onto terrain
    dna = brief["dna"]
    layout["terrain"] = {
        **(layout.get("terrain") or {}),
        "maxHeight": dna["max_height"],
        "waterLevel": dna["water_level"],
        "worldScale": dna["world_scale"],
        "vegetation": dna["vegetation"],
        "shape": dna["shape"],
    }
    layout["mapBrief"] = {
        "premise": brief["premise"],
        "palette": dna["palette"],
        "dit_prompt": brief["dit_prompt"],
        "source": "pending",
    }
    layout["name"] = brief["name"]
    layout["genre"] = civ

    json_path = OUT_MAPS / f"{civ}.json"

    png_path = OUT_MAPS / f"{civ}.png"
    painted = False
    if use_dit:
        painted = paint_dit(civ, png_path)
    if not painted:
        paint_procedural(civ, layout).save(png_path, "PNG")
    layout["mapBrief"]["source"] = "hunyuan_dit" if painted else "procedural_distinct"
    json_path.write_text(json.dumps(layout, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # mirror under civilization pack
    civ_map = CIV_ROOT / civ / "map"
    civ_map.mkdir(parents=True, exist_ok=True)
    (civ_map / "layout.json").write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
    (civ_map / "overview.png").write_bytes(png_path.read_bytes())
    (civ_map / "brief.json").write_text(
        json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    (RUNTIME / f"{civ}.json").write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
    (RUNTIME / f"{civ}.png").write_bytes(png_path.read_bytes())

    return {
        "civ": civ,
        "name": brief["name"],
        "png": str(png_path.relative_to(ROOT)),
        "json": str(json_path.relative_to(ROOT)),
        "dit": painted,
        "scale": dna["world_scale"],
        "maxHeight": dna["max_height"],
        "vegetation": dna["vegetation"],
        "cities": len(layout.get("cities") or []),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dit", action="store_true", help="Paint overview with HunyuanDiT")
    ap.add_argument("--civ", default="", help="Single civilization key")
    args = ap.parse_args()

    civs = [args.civ] if args.civ else list(MAP_DNA.keys())
    # ensure GENRE_META has all
    missing = [c for c in civs if c not in GENRE_META]
    if missing:
        raise SystemExit(f"layout GENRE_META missing: {missing}")

    index = []
    for civ in civs:
        print(f"== {civ} ==")
        info = generate_one(civ, use_dit=args.dit)
        index.append(info)
        print(
            f"  ok scale={info['scale']} h={info['maxHeight']} "
            f"veg={info['vegetation'][:20]} dit={info['dit']} cities={info['cities']}"
        )

    (OUT_MAPS / "index.json").write_text(
        json.dumps({"maps": index}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"wrote {len(index)} maps → {OUT_MAPS}")


if __name__ == "__main__":
    main()
