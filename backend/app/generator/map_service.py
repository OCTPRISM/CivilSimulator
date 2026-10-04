"""Civilization-aware map generation (distinct DNA + optional HunyuanDiT paint)."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from ..config import get_settings
from .civilization_maps import MAP_DNA, map_brief, paint_style_for

W, H = 960, 540

ROOT = Path(__file__).resolve().parents[2]
VENV_PY = ROOT / ".venv-hunyuan3d" / "bin" / "python3"
T2I_CLI = ROOT / "scripts" / "hunyuan3d" / "text_to_image_cli.py"
PUBLIC_MAPS = ROOT.parent / "frontend" / "public" / "maps"


def infer_genre(prompt: str, override: str | None = None) -> str:
    if override and override in MAP_DNA:
        return override
    lower = (prompt or "").lower()
    scores = {g: 0 for g in MAP_DNA}
    keywords = {
        "wuxia": ("武侠", "江湖", "门派", "风波"),
        "ancient": ("古代", "长安", "汉", "唐", "九州"),
        "modern": ("现代", "都市", "都会", "听证"),
        "scifi": ("科幻", "太空", "环带", "轨道"),
        "xuanhuan": ("玄幻", "仙", "灵", "九霄"),
        "mystery": ("雾港", "悬疑", "1931", "侦探"),
        "enterprise": ("创业", "融资", "青梧", "路演"),
        "securities": ("证券", "交易", "镜湖", "散户"),
        "military": ("边关", "军事", "前线", "后勤"),
    }
    for g, kws in keywords.items():
        scores[g] = sum(1 for kw in kws if kw in prompt or kw in lower)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "wuxia"


def _slug(prompt: str, civ: str) -> str:
    h = hashlib.sha256(f"{civ}:{prompt}".encode()).hexdigest()[:10]
    return f"{civ}-{h}"


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
    elif shape == "floating_isles":
        base = np.maximum(base * 0.5, np.exp(-((nx - 0.5) ** 2 + (ny - 0.35) ** 2) * 6) * 0.65)
    elif shape == "river_plains":
        base *= 0.55
        base += np.exp(-((nx - 0.5) ** 2 + (ny - 0.22) ** 2) * 18) * 0.18
    elif shape == "fog_harbor":
        base *= 0.45
        base[int(H * 0.7):, :] *= 0.3
    elif shape == "city_grid":
        base *= 0.35 + 0.1 * scale
    elif shape == "orbital_hub":
        rr = np.sqrt((nx - 0.5) ** 2 + (ny - 0.48) ** 2)
        base = 0.25 + 0.35 * np.exp(-((rr - 0.22) ** 2) * 40)
    elif shape == "campus_plateau":
        base = np.clip(0.35 + 0.08 * np.sin(nx * 12) * np.cos(ny * 10), 0.25, 0.55)
    elif shape == "lake_finance":
        base *= 0.3
        lake = np.exp(-((nx - 0.5) ** 2 / 0.12 + (ny - 0.65) ** 2 / 0.05))
        base = base * (1 - 0.7 * lake)
    elif shape == "canyon_front":
        base += np.exp(-((nx - 0.35) ** 2) * 8) * 0.5
        base += np.exp(-((nx - 0.72) ** 2 + (ny - 0.55) ** 2) * 10) * 0.4
    return np.clip(base, 0, 1)


def _paint_procedural(civ: str, prompt: str, locs: list[dict[str, Any]]) -> Image.Image:
    brief = map_brief(civ)
    dna = brief["dna"]
    st = paint_style_for(civ)
    seed = int(hashlib.md5(f"{civ}:{prompt}".encode()).hexdigest()[:8], 16)
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
    draw = ImageDraw.Draw(img)
    for loc in locs:
        lx, ly = int(float(loc["x"]) * W), int(float(loc["y"]) * H)
        draw.ellipse((lx - 6, ly - 6, lx + 6, ly + 6), fill=st["accent"], outline=st["label"])
        draw.text((lx + 8, ly - 6), str(loc["name"])[:12], fill=st["label"])
    draw.rectangle((0, 0, W, 26), fill=tuple(max(0, c - 25) for c in st["sky"]))
    draw.text((10, 6), f"{brief['name']} · {dna['vegetation'][:18]}", fill=st["label"])
    return img.filter(ImageFilter.GaussianBlur(radius=0.4))


def _try_dit(prompt: str, out: Path, seed: int) -> bool:
    cfg = get_settings()
    if getattr(cfg, "hunyuan3d_text2img_mode", "lite") != "dit":
        return False
    if not VENV_PY.is_file() or not T2I_CLI.is_file():
        return False
    import os
    env = {
        **os.environ,
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "PYTHONUNBUFFERED": "1",
    }
    cmd = [
        str(VENV_PY), "-u", str(T2I_CLI), prompt[:200],
        "-o", str(out),
        "--device", cfg.hunyuan3d_device,
        "--seed", str(seed),
        "--kind", "map",
        "--steps", "12",
        "--size", "768",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600, env=env)
    except Exception:
        return False
    return proc.returncode == 0 and out.is_file()


def generate_map(prompt: str, genre: str | None = None) -> dict[str, Any]:
    civ = infer_genre(prompt, genre)
    brief = map_brief(civ)
    dna = brief["dna"]
    seed = int(hashlib.md5(f"{civ}:{prompt}".encode()).hexdigest()[:8], 16)
    slug = _slug(prompt, civ)

    settings = get_settings()
    out_dir = Path(settings.generator_output_dir) / "maps"
    out_dir.mkdir(parents=True, exist_ok=True)
    png_path = out_dir / f"{slug}.png"
    json_path = out_dir / f"{slug}.json"

    # Prefer curated play-map locations when prompt is the civ itself
    locs: list[dict[str, Any]] = []
    curated = PUBLIC_MAPS / f"{civ}.json"
    if curated.is_file() and (not prompt.strip() or prompt.strip() in (civ, brief["name"])):
        data = json.loads(curated.read_text(encoding="utf-8"))
        for loc in data.get("locations") or []:
            locs.append({
                "id": f"loc_{len(locs)}",
                "name": loc["name"],
                "x": round(float(loc["x"]) / W, 3),
                "y": round(float(loc["y"]) / H, 3),
            })
    if not locs:
        names = brief["locations"] or [f"{brief['name']}·核心"]
        for i, name in enumerate(names[:6]):
            locs.append({
                "id": f"loc_{i}",
                "name": name,
                "x": round(0.18 + (i % 3) * 0.28, 3),
                "y": round(0.25 + (i // 3) * 0.35, 3),
            })

    dit_tmp = out_dir / f"{slug}.dit.png"
    painted = _try_dit(brief["dit_prompt"] if len(prompt) < 8 else f"{brief['dit_prompt']},{prompt}"[:200], dit_tmp, seed)
    if painted:
        Image.open(dit_tmp).convert("RGB").resize((W, H)).save(png_path, "PNG")
        dit_tmp.unlink(missing_ok=True)
        source = "hunyuan_dit"
    else:
        _paint_procedural(civ, prompt, locs).save(png_path, "PNG")
        source = "procedural_distinct"

    meta = {
        "slug": slug,
        "prompt": prompt,
        "genre": civ,
        "civilization": civ,
        "width": W,
        "height": H,
        "locations": locs,
        "factions": [],
        "terrain": {
            "seed": seed,
            "maxHeight": dna["max_height"],
            "waterLevel": dna["water_level"],
            "worldScale": dna["world_scale"],
            "vegetation": dna["vegetation"],
            "shape": dna["shape"],
        },
        "mapBrief": {
            "name": brief["name"],
            "premise": brief["premise"],
            "palette": dna["palette"],
            "source": source,
        },
        "landmarks": [{"name": loc["name"], "x": loc["x"], "y": loc["y"]} for loc in locs[:3]],
    }
    json_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    pub_dir = ROOT.parent / "frontend/public/generated/maps"
    pub_dir.mkdir(parents=True, exist_ok=True)
    (pub_dir / f"{slug}.png").write_bytes(png_path.read_bytes())

    return {
        "slug": slug,
        "prompt": prompt,
        "genre": civ,
        "civilization": civ,
        "png_url": f"/generated/maps/{slug}.png",
        "json_url": f"/api/generator/maps/{slug}/meta.json",
        "locations": locs,
        "source": source,
    }
