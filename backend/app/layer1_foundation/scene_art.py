"""M3 scene illustration plates — fast local Pillow atmospheres (no GPU).

Generates cinematic gradient plates keyed by genre / location / hour / tension,
cached under data/runtime/scene_art/.
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from ..config import get_settings

log = logging.getLogger(__name__)

_PALETTES: dict[str, tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]] = {
    "ancient": ((28, 22, 18), (92, 58, 36), (196, 154, 92)),
    "wuxia": ((18, 24, 32), (36, 64, 78), (140, 168, 188)),
    "xianxia": ((16, 18, 40), (48, 36, 88), (180, 140, 210)),
    "scifi": ((8, 12, 22), (20, 48, 72), (80, 200, 220)),
    "mystery": ((12, 10, 14), (40, 28, 36), (120, 90, 70)),
    "default": ((16, 16, 20), (48, 48, 56), (160, 150, 130)),
}


def _palette(genre: str) -> tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]:
    return _PALETTES.get((genre or "default").lower(), _PALETTES["default"])


def _lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


_FONT_CANDIDATES = (
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
)


def _load_fonts(size: int, size_s: int):
    """Prefer CJK-capable system fonts; fall back to PIL default."""
    from PIL import ImageFont

    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size), ImageFont.truetype(path, size_s)
        except Exception:
            continue
    default = ImageFont.load_default()
    return default, default


def _cache_key(genre: str, location: str, hour: float, tension: float, summary: str) -> str:
    raw = f"{genre}|{location}|{hour:.1f}|{tension:.2f}|{summary[:80]}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def scene_art_dir() -> Path:
    s = get_settings()
    root = Path(s.data_dir) / "scene_art"
    root.mkdir(parents=True, exist_ok=True)
    return root


def generate_scene_plate(
    *,
    genre: str = "ancient",
    location_name: str = "",
    summary: str = "",
    hour: float = 12.0,
    tension: float = 0.3,
    width: int = 1280,
    height: int = 720,
) -> Path:
    """Return path to a PNG plate (cached)."""
    from PIL import Image, ImageDraw, ImageFilter

    key = _cache_key(genre, location_name, hour, tension, summary)
    out = scene_art_dir() / f"{key}.png"
    if out.exists() and out.stat().st_size > 0:
        return out

    base, mid, accent = _palette(genre)
    # Night / dawn / dusk shifts
    h = hour % 24.0
    if h < 5 or h >= 20:
        base = _lerp(base, (6, 8, 18), 0.55)
        mid = _lerp(mid, (20, 28, 50), 0.45)
    elif h < 8 or h >= 17:
        mid = _lerp(mid, accent, 0.35)
        accent = _lerp(accent, (220, 140, 80), 0.4)

    # Tension warms toward crimson
    if tension > 0.45:
        t = min(1.0, (tension - 0.45) / 0.55)
        mid = _lerp(mid, (110, 36, 36), t * 0.6)
        accent = _lerp(accent, (180, 60, 50), t * 0.5)

    img = Image.new("RGB", (width, height), base)
    px = img.load()
    assert px is not None
    for y in range(height):
        ty = y / max(1, height - 1)
        # Vertical gradient + subtle vignette horizontal
        c = _lerp(base, mid, ty ** 0.85)
        c = _lerp(c, accent, (ty ** 2) * 0.35)
        for x in range(width):
            tx = abs(x / max(1, width - 1) - 0.5) * 2
            v = _lerp(c, base, tx * 0.25)
            # Soft noise
            n = ((x * 17 + y * 31) % 17) - 8
            px[x, y] = (
                max(0, min(255, v[0] + n)),
                max(0, min(255, v[1] + n // 2)),
                max(0, min(255, v[2] + n // 3)),
            )

    # Atmospheric bands (horizon haze)
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    horizon = int(height * (0.55 - min(0.15, tension * 0.1)))
    for i in range(40):
        alpha = int(18 + i * 1.2)
        y0 = horizon - 20 + i * 3
        col = (*accent, max(0, min(60, alpha)))
        draw.rectangle([0, y0, width, y0 + 4], fill=col)
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    img = img.filter(ImageFilter.GaussianBlur(radius=0.8))

    # Title plate
    draw2 = ImageDraw.Draw(img)
    title = (location_name or "未知之地").strip()[:24]
    sub = (summary or "").strip()[:48]
    font, font_s = _load_fonts(42, 22)
    # Shadow text
    tx, ty = 48, height - 120
    draw2.text((tx + 2, ty + 2), title, fill=(0, 0, 0), font=font)
    draw2.text((tx, ty), title, fill=(240, 230, 210), font=font)
    if sub:
        draw2.text((tx + 1, ty + 52), sub, fill=(0, 0, 0), font=font_s)
        draw2.text((tx, ty + 50), sub, fill=(200, 190, 170), font=font_s)

    tmp = out.with_suffix(".tmp.png")
    img.save(tmp, format="PNG", optimize=True)
    tmp.replace(out)
    log.info("scene art plate %s (%s / %s)", out.name, genre, location_name)
    return out


def plate_url_path(path: Path) -> str:
    """Public URL path served by FastAPI static mount."""
    return f"/api/media/scene-art/file/{path.name}"
