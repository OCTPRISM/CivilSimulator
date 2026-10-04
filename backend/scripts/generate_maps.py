"""Generate stylised top-down PNG maps for each civilization seed.

Output:
  frontend/public/maps/<seed>.png      — 960x540 stylised map
  frontend/public/maps/<seed>.json     — { width,height, locations:[{name,x,y}],
                                           factions:[{name,x,y,r,color}] }

Pure CPU (Pillow + numpy). Re-run anytime with:
    python -m scripts.generate_maps
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

BACKEND = Path(__file__).resolve().parent.parent
SEEDS_DIR = BACKEND / "app" / "seeds"
OUT_DIR = BACKEND.parent / "frontend" / "public" / "maps"
OUT_DIR.mkdir(parents=True, exist_ok=True)

W, H = 960, 540

# Per-genre style: terrain palette and motif (river / craters / etc.)
STYLE = {
    "ancient": {
        "sky":      (60, 50, 40),
        "land_low": (90, 76, 52),
        "land_hi":  (140, 120, 86),
        "water":    (52, 76, 96),
        "road":     (180, 156, 110),
        "accent":   (220, 190, 120),
        "label":    (240, 224, 180),
        "shape":    "river_plains",   # great river, walled cities
        "road_width": 3,
    },
    "modern": {
        "sky":      (72, 110, 148),
        "land_low": (88, 98, 78),
        "land_hi":  (130, 138, 108),
        "water":    (40, 96, 128),
        "road":     (55, 58, 62),
        "accent":   (250, 210, 90),
        "label":    (250, 250, 252),
        "shape":    "city_grid",
        "road_width": 5,
    },
    "wuxia": {
        "sky":      (38, 32, 44),
        "land_low": (62, 80, 64),
        "land_hi":  (124, 152, 110),
        "water":    (60, 84, 110),
        "road":     (200, 170, 110),
        "accent":   (244, 196, 124),
        "label":    (240, 220, 196),
        "shape":    "rivers_and_peaks",
        "road_width": 3,
    },
    "xuanhuan": {
        "sky":      (24, 18, 48),
        "land_low": (60, 40, 92),
        "land_hi":  (120, 78, 168),
        "water":    (48, 30, 92),
        "road":     (236, 200, 255),
        "accent":   (250, 210, 130),
        "label":    (240, 224, 255),
        "shape":    "floating_isles",
        "road_width": 3,
    },
    "scifi": {
        "sky":      (8, 16, 28),
        "land_low": (24, 44, 60),
        "land_hi":  (60, 110, 150),
        "water":    (8, 24, 40),
        "road":     (120, 220, 240),
        "accent":   (120, 220, 240),
        "label":    (200, 230, 250),
        "shape":    "orbital_ring",
        "road_width": 3,
    },
    "mystery": {
        "sky":      (16, 16, 22),
        "land_low": (38, 36, 44),
        "land_hi":  (78, 72, 84),
        "water":    (24, 28, 38),
        "road":     (170, 150, 110),
        "accent":   (200, 100, 100),
        "label":    (220, 210, 200),
        "shape":    "harbour_grid",
        "road_width": 3,
    },
}


def value_noise(w: int, h: int, scale: int, rng: np.random.Generator) -> np.ndarray:
    """Cheap value noise: random low-res grid → bicubic upscale via PIL."""
    sw, sh = max(2, w // scale), max(2, h // scale)
    grid = rng.random((sh, sw), dtype=np.float32)
    img = Image.fromarray((grid * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
    arr = np.asarray(img, dtype=np.float32) / 255.0
    return arr


def fbm(w: int, h: int, octaves: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w), dtype=np.float32)
    amp, total = 1.0, 0.0
    for o in range(octaves):
        scale = 2 ** (5 - o)  # bigger blobs first
        out += amp * value_noise(w, h, scale, rng)
        total += amp
        amp *= 0.55
    out /= total
    # normalise
    out -= out.min()
    out /= max(1e-6, out.max())
    return out


def lerp_color(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ------------------------------------------------------------------
# Per-shape composers
# ------------------------------------------------------------------
def compose_terrain(genre: str, seed: int) -> Image.Image:
    s = STYLE.get(genre, STYLE["ancient"])
    height = fbm(W, H, octaves=5, seed=seed)
    img = Image.new("RGB", (W, H), s["sky"])
    px = img.load()

    if s["shape"] == "river_plains":
        # river snaking horizontally
        rng = np.random.default_rng(seed + 1)
        river_y = H * 0.55 + 40 * np.sin(np.linspace(0, 5, W) + rng.random()*3)
    elif s["shape"] == "rivers_and_peaks":
        rng = np.random.default_rng(seed + 7)
        river_y = H * 0.62 + 50 * np.sin(np.linspace(0, 7, W) + rng.random()*3)
    elif s["shape"] == "city_grid":
        rng = np.random.default_rng(seed + 11)
        river_y = H * 0.70 + 28 * np.sin(np.linspace(0, 4, W) + rng.random()*2)
    elif s["shape"] == "floating_isles":
        river_y = None
    elif s["shape"] == "orbital_ring":
        river_y = None
    elif s["shape"] == "harbour_grid":
        # harbour: bottom third is water
        river_y = None
    else:
        river_y = None

    for y in range(H):
        for x in range(W):
            v = height[y, x]
            if s["shape"] == "harbour_grid" and y > H * 0.62:
                px[x, y] = s["water"]
                continue
            if s["shape"] == "floating_isles":
                # threshold makes islands; rest is sky
                if v < 0.55:
                    # deep purple sky with stars later
                    px[x, y] = lerp_color(s["sky"], s["water"], 0.3)
                    continue
                t = (v - 0.55) / 0.45
                px[x, y] = lerp_color(s["land_low"], s["land_hi"], t)
                continue
            if s["shape"] == "orbital_ring":
                # ring band
                cy, cx = H/2, W/2
                d = math.hypot(x - cx, (y - cy)*1.4)
                if 170 < d < 230:
                    t = (d - 170) / 60
                    px[x, y] = lerp_color(s["land_low"], s["land_hi"], t)
                else:
                    # space starfield base
                    px[x, y] = lerp_color(s["sky"], s["water"], v*0.6)
                continue
            # default: land with optional river
            if river_y is not None and abs(y - river_y[x]) < 14 - 8*v:
                px[x, y] = s["water"]
            else:
                px[x, y] = lerp_color(s["land_low"], s["land_hi"], v)
    return img


def add_starfield(img: Image.Image, density: float, color, seed: int):
    rng = random.Random(seed)
    draw = ImageDraw.Draw(img)
    n = int(W * H * density)
    for _ in range(n):
        x = rng.randint(0, W - 1)
        y = rng.randint(0, H - 1)
        b = rng.randint(120, 255)
        draw.point((x, y), fill=(color[0], color[1], min(255, b)))


def add_grid(img: Image.Image, color, step=40, alpha=40):
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    rgba = (*color, alpha)
    for x in range(0, W, step):
        d.line([(x, 0), (x, H)], fill=rgba, width=1)
    for y in range(0, H, step):
        d.line([(0, y), (W, y)], fill=rgba, width=1)
    img.alpha_composite(overlay) if img.mode == "RGBA" else img.paste(
        Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB"))


# ------------------------------------------------------------------
# Layout: place locations & factions on the map
# ------------------------------------------------------------------
def layout(genre: str, locs: list[dict], facs: list[dict], seed: int) -> dict:
    rng = random.Random(seed + 42)
    s = STYLE.get(genre, STYLE["ancient"])
    pts: list[tuple[int, int]] = []
    if s["shape"] == "orbital_ring":
        # Place locations around the ring
        cx, cy = W/2, H/2
        for i in range(len(locs)):
            ang = (i / max(1, len(locs))) * 2*math.pi - math.pi/2
            r = 200
            pts.append((int(cx + math.cos(ang)*r), int(cy + math.sin(ang)*r*0.7)))
    elif s["shape"] == "floating_isles":
        for _ in range(len(locs)):
            pts.append((rng.randint(160, W-160), rng.randint(120, H-120)))
    elif s["shape"] == "harbour_grid":
        # locations on the land (top 60%), spaced
        gap = W // (len(locs) + 1)
        for i in range(len(locs)):
            pts.append((gap*(i+1), int(H*0.35) + rng.randint(-30, 30)))
    elif s["shape"] == "city_grid":
        gap = W // (len(locs) + 1)
        for i in range(len(locs)):
            x = gap * (i + 1) + rng.randint(-20, 20)
            y = int(H * (0.32 + 0.08 * i)) + rng.randint(-25, 25)
            pts.append((x, max(90, min(H - 160, y))))
    else:
        # river plains / wuxia: spread across the map
        gap = W // (len(locs) + 1)
        for i in range(len(locs)):
            x = gap * (i + 1) + rng.randint(-30, 30)
            y = int(H * 0.4) + rng.randint(-90, 90)
            pts.append((x, y))

    location_records = [
        {"name": l["name"], "x": p[0], "y": p[1]}
        for l, p in zip(locs, pts)
    ]
    # Factions = blobs at random positions, semi-transparent territory
    palette = [
        (210, 110, 110), (110, 170, 210), (200, 180, 100),
        (160, 200, 130), (180, 120, 200), (110, 200, 180),
    ]
    faction_records = []
    for i, f in enumerate(facs):
        # anchor near a different point if possible
        anchor = pts[i % len(pts)] if pts else (W//2, H//2)
        ox = rng.randint(-140, 140)
        oy = rng.randint(-90, 90)
        fx = max(80, min(W-80, anchor[0] + ox))
        fy = max(60, min(H-60, anchor[1] + oy))
        faction_records.append({
            "name": f["name"],
            "x": fx, "y": fy,
            "r": rng.randint(110, 170),
            "color": palette[i % len(palette)],
        })
    return {"locations": location_records, "factions": faction_records}


# ------------------------------------------------------------------
# Annotate the map
# ------------------------------------------------------------------
def draw_factions(img: Image.Image, factions: list[dict]):
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for f in factions:
        r = f["r"]
        c = (*f["color"], 60)
        d.ellipse([f["x"]-r, f["y"]-r, f["x"]+r, f["y"]+r], fill=c)
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=18))
    img.alpha_composite(overlay)


def draw_roads(img: Image.Image, locations: list[dict], color, width: int = 3):
    if len(locations) < 2:
        return
    d = ImageDraw.Draw(img, "RGBA")
    for a, b in zip(locations, locations[1:]):
        d.line([(a["x"], a["y"]), (b["x"], b["y"])],
               fill=(*color, 190), width=width)
    a, b = locations[-1], locations[0]
    d.line([(a["x"], a["y"]), (b["x"], b["y"])],
           fill=(*color, 70), width=max(2, width - 1))


def draw_ship_ports(img: Image.Image, genre: str, locations: list[dict]):
    """Sci-fi: circular docking pads near later locations."""
    if genre != "scifi":
        return
    d = ImageDraw.Draw(img, "RGBA")
    for loc in locations[1:]:
        x, y = loc["x"], loc["y"] + 40
        r = 36
        d.ellipse([x - r, y - r, x + r, y + r], outline=(80, 220, 240, 200), width=3)
        d.ellipse([x - r + 10, y - r + 10, x + r - 10, y + r - 10],
                  outline=(40, 180, 220, 140), width=2)
        d.ellipse([x - 6, y - 6, x + 6, y + 6], fill=(120, 230, 255, 180))


def draw_city_walls(img: Image.Image, locations: list[dict], genre: str):
    """Ancient / wuxia: oval walls + moat rings around urban location pins."""
    if genre not in ("ancient", "wuxia") or not locations:
        return
    d = ImageDraw.Draw(img, "RGBA")
    for loc in locations[:2]:
        x, y = loc["x"], loc["y"]
        rx, ry = 70, 52
        # moat (ancient only)
        if genre == "ancient":
            d.ellipse([x - rx - 14, y - ry - 12, x + rx + 14, y + ry + 12],
                      outline=(40, 70, 100, 160), width=6)
            d.ellipse([x - rx - 8, y - ry - 6, x + rx + 8, y + ry + 6],
                      fill=(45, 80, 110, 55))
        # wall
        d.ellipse([x - rx, y - ry, x + rx, y + ry],
                  outline=(90, 80, 65, 210), width=4)
        d.ellipse([x - rx + 5, y - ry + 4, x + rx - 5, y + ry - 4],
                  outline=(130, 115, 90, 120), width=2)


def get_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/Library/Fonts/Songti.ttc",
        "/System/Library/Fonts/Supplemental/Songti.ttc",
    ]
    for c in candidates:
        try:
            return ImageFont.truetype(c, size)
        except Exception:
            continue
    return ImageFont.load_default()


def draw_pins(img: Image.Image, locations: list[dict], factions: list[dict],
              accent, label_color):
    d = ImageDraw.Draw(img, "RGBA")
    fnt_loc = get_font(16)
    fnt_fac = get_font(13)

    # Faction labels (lighter, larger)
    for f in factions:
        d.text((f["x"]+4, f["y"]-8), f["name"],
               font=fnt_fac, fill=(*f["color"], 220),
               stroke_width=2, stroke_fill=(0, 0, 0, 180))

    # Location pins (bright dot + ring + label)
    for l in locations:
        x, y = l["x"], l["y"]
        d.ellipse([x-12, y-12, x+12, y+12],
                  outline=(*accent, 220), width=2)
        d.ellipse([x-5, y-5, x+5, y+5], fill=(*accent, 255))
        # label background
        text = l["name"]
        bbox = d.textbbox((0, 0), text, font=fnt_loc)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        bx, by = x + 14, y - th - 6
        d.rounded_rectangle([bx - 4, by - 4, bx + tw + 6, by + th + 6],
                            radius=6, fill=(0, 0, 0, 180))
        d.text((bx, by), text, font=fnt_loc, fill=(*label_color, 255))


def draw_compass_and_title(img: Image.Image, title: str, genre: str, accent):
    d = ImageDraw.Draw(img, "RGBA")
    fnt_title = get_font(22)
    fnt_sub = get_font(12)
    # title plate top-left
    d.rounded_rectangle([16, 16, 280, 64], radius=8, fill=(0, 0, 0, 160))
    d.text((26, 22), title, font=fnt_title, fill=(*accent, 255))
    d.text((26, 48), genre.upper(), font=fnt_sub, fill=(*accent, 200))
    # compass top-right
    cx, cy = W - 60, 50
    d.ellipse([cx-26, cy-26, cx+26, cy+26], outline=(*accent, 200), width=2)
    d.line([(cx, cy-20), (cx, cy+20)], fill=(*accent, 220), width=2)
    d.line([(cx-20, cy), (cx+20, cy)], fill=(*accent, 120), width=1)
    d.text((cx-4, cy-38), "N", font=fnt_sub, fill=(*accent, 220))


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
def render_seed(seed_path: Path) -> None:
    data = json.loads(seed_path.read_text(encoding="utf-8"))
    key = data["key"]
    genre = data.get("genre", key)
    s = STYLE.get(genre, STYLE["ancient"])

    rng_seed = sum(ord(c) for c in key) * 17
    img = compose_terrain(genre, rng_seed).convert("RGBA")

    if s["shape"] in ("orbital_ring", "floating_isles"):
        add_starfield(img, density=0.0008,
                      color=(220, 220, 255), seed=rng_seed)

    lay = layout(genre, data["locations"], data["factions"], rng_seed)
    draw_factions(img, lay["factions"])
    draw_roads(img, lay["locations"], s["road"], width=s.get("road_width", 3))
    draw_city_walls(img, lay["locations"], genre)
    draw_ship_ports(img, genre, lay["locations"])
    if s["shape"] == "city_grid":
        add_grid(img, s["road"], step=48, alpha=28)
    draw_pins(img, lay["locations"], lay["factions"],
              accent=s["accent"], label_color=s["label"])
    draw_compass_and_title(img, data["name"], genre, s["accent"])

    # vignette
    vignette = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vignette)
    for i in range(60):
        a = int(2 + i * 0.6)
        vd.rectangle([i, i, W-i, H-i], outline=(0, 0, 0, a))
    img = Image.alpha_composite(img, vignette)

    out_png = OUT_DIR / f"{key}.png"
    img.convert("RGB").save(out_png, optimize=True)
    out_json = OUT_DIR / f"{key}.json"
    meta = {
        "width": W, "height": H,
        "name": data["name"], "genre": genre,
        "locations": lay["locations"],
        "factions": lay["factions"],
    }
    # Preserve hand-enriched 3D layout fields when regenerating
    if out_json.exists():
        try:
            prev = json.loads(out_json.read_text(encoding="utf-8"))
            for k in ("terrain", "water", "trees", "buildings", "animals", "roads", "walls"):
                if k in prev:
                    meta[k] = prev[k]
            # Keep authored location coords / enterable flags when names match
            by_name = {l["name"]: l for l in prev.get("locations", [])}
            if by_name:
                merged = []
                for loc in lay["locations"]:
                    old = by_name.get(loc["name"])
                    merged.append({**loc, **({k: old[k] for k in ("x", "y", "building", "enterable") if k in old} if old else {})})
                meta["locations"] = merged
            # Keep faction terrain tags / authored positions
            fac_by_name = {f["name"]: f for f in prev.get("factions", [])}
            if fac_by_name:
                merged_f = []
                for f in lay["factions"]:
                    old = fac_by_name.get(f["name"], {})
                    merged_f.append({
                        **f,
                        **({k: old[k] for k in ("x", "y", "r", "terrain", "color") if k in old}),
                    })
                meta["factions"] = merged_f
        except Exception:
            pass
    out_json.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  wrote {out_png.name} + {out_json.name}")


def main() -> None:
    print(f"Output dir: {OUT_DIR}")
    for f in sorted(SEEDS_DIR.glob("*.json")):
        print(f"Rendering {f.stem} …")
        render_seed(f)
    print("Done.")


if __name__ == "__main__":
    main()
