"""Lightweight text → reference PNG (no DiT download). Feeds Hunyuan3D shape pipeline.

Draws recognizable orthographic / 3⁄4 silhouettes so image→mesh gets real volume
instead of abstract color blobs.
"""
from __future__ import annotations

import hashlib
import io
import re

from PIL import Image, ImageDraw


def _palette(prompt: str, kind: str) -> tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]:
    h = int(hashlib.md5((prompt + kind).encode()).hexdigest()[:8], 16)
    wood = (110 + (h % 40), 70 + ((h >> 4) % 30), 45 + ((h >> 8) % 25))
    roof = (140 + ((h >> 10) % 50), 55 + ((h >> 14) % 40), 50 + ((h >> 18) % 30))
    wall = (235, 228, 210)
    return wood, roof, wall


def _draw_building(draw: ImageDraw.ImageDraw, size: int, prompt: str) -> None:
    wood, roof, wall = _palette(prompt, "building")
    cx = size // 2
    # stone platform (depth)
    draw.polygon([(cx - 170, 390), (cx + 150, 390), (cx + 190, 430), (cx - 130, 430)], fill=(160, 150, 140))
    draw.rectangle((cx - 150, 400, cx + 160, 420), fill=(130, 120, 110))
    # main hall body with side depth
    draw.polygon([(cx - 130, 220), (cx + 90, 220), (cx + 140, 250), (cx + 140, 400), (cx - 130, 400)], fill=wall)
    draw.polygon([(cx + 90, 220), (cx + 150, 200), (cx + 190, 230), (cx + 140, 250)], fill=(210, 200, 180))
    draw.polygon([(cx + 140, 250), (cx + 190, 230), (cx + 190, 380), (cx + 140, 400)], fill=(190, 175, 155))
    # pillars
    for x in (cx - 110, cx - 40, cx + 30, cx + 70):
        draw.rectangle((x, 250, x + 18, 400), fill=wood)
    # door
    draw.rectangle((cx - 25, 310, cx + 25, 400), fill=(90, 40, 35))
    # windows
    for x in (cx - 95, cx + 45):
        draw.rectangle((x, 280, x + 36, 330), fill=(180, 200, 210), outline=wood, width=2)
    # curved tile roof (front + side)
    draw.polygon(
        [(cx - 160, 230), (cx - 20, 150), (cx + 110, 230), (cx + 90, 250), (cx - 130, 250)],
        fill=roof,
    )
    draw.polygon(
        [(cx + 110, 230), (cx + 170, 180), (cx + 200, 210), (cx + 140, 250)],
        fill=(max(roof[0] - 25, 40), max(roof[1] - 15, 30), max(roof[2] - 10, 30)),
    )
    # ridge ornament
    draw.ellipse((cx - 35, 140, cx + 5, 170), fill=(200, 160, 60))
    if re.search(r"palace|殿|紫宸", prompt, re.I):
        # second roof tier
        draw.polygon(
            [(cx - 120, 200), (cx - 10, 130), (cx + 90, 200), (cx + 70, 215), (cx - 100, 215)],
            fill=(max(roof[0] - 10, 40), max(roof[1] + 20, 40), 40),
        )
    if re.search(r"tavern|酒|楼", prompt, re.I):
        # balcony + banner
        draw.rectangle((cx - 100, 260, cx + 80, 275), fill=wood)
        draw.rectangle((cx + 55, 240, cx + 75, 320), fill=(180, 30, 30))


def _draw_stall(draw: ImageDraw.ImageDraw, size: int, prompt: str) -> None:
    wood, roof, _ = _palette(prompt, "stall")
    cx, cy = size // 2, size // 2 + 40
    # legs + table
    for x in (cx - 110, cx + 90):
        draw.rectangle((x, cy, x + 14, cy + 90), fill=wood)
    draw.polygon([(cx - 130, cy), (cx + 110, cy), (cx + 130, cy + 25), (cx - 110, cy + 25)], fill=(150, 110, 70))
    # awning poles + canopy (depth)
    for x in (cx - 120, cx + 100):
        draw.rectangle((x, cy - 140, x + 10, cy), fill=wood)
    awn = roof if not re.search(r"cloth|布", prompt) else (40, 90, 160)
    if re.search(r"bing|饼|food|胡", prompt, re.I):
        awn = (210, 120, 50)
    if re.search(r"book|书", prompt):
        awn = (120, 90, 60)
    if re.search(r"wine|酒", prompt):
        awn = (160, 40, 40)
    if re.search(r"spice|香", prompt):
        awn = (180, 100, 40)
    draw.polygon(
        [(cx - 140, cy - 130), (cx + 120, cy - 150), (cx + 140, cy - 90), (cx - 120, cy - 70)],
        fill=awn,
    )
    # goods piles
    goods = [(200, 80, 60), (240, 180, 40), (80, 140, 70), (180, 60, 40)]
    for i, c in enumerate(goods):
        x = cx - 90 + i * 50
        draw.ellipse((x, cy - 35, x + 40, cy + 5), fill=c)
        draw.ellipse((x + 5, cy - 50, x + 35, cy - 20), fill=c)


def _draw_prop(draw: ImageDraw.ImageDraw, size: int, prompt: str) -> None:
    wood, roof, wall = _palette(prompt, "prop")
    cx, cy = size // 2, size // 2
    p = prompt.lower()
    if re.search(r"lantern|灯", p):
        draw.rectangle((cx - 8, cy - 40, cx + 8, cy + 160), fill=wood)
        draw.ellipse((cx - 45, cy - 120, cx + 45, cy - 20), fill=(250, 210, 100), outline=(180, 120, 40), width=3)
        draw.rectangle((cx - 50, cy - 125, cx + 50, cy - 110), fill=wood)
    elif re.search(r"banner|旗|幡", p):
        draw.rectangle((cx - 8, cy - 160, cx + 8, cy + 160), fill=wood)
        draw.polygon([(cx + 8, cy - 140), (cx + 90, cy - 120), (cx + 90, cy + 40), (cx + 8, cy + 20)], fill=(180, 30, 30))
    elif re.search(r"lion|狮", p):
        draw.rectangle((cx - 70, cy + 60, cx + 70, cy + 120), fill=(170, 165, 160))
        draw.ellipse((cx - 55, cy - 40, cx + 55, cy + 80), fill=(190, 185, 180))
        draw.ellipse((cx - 35, cy - 100, cx + 45, cy - 20), fill=(185, 180, 175))
        draw.ellipse((cx + 25, cy - 90, cx + 70, cy - 40), fill=(175, 170, 165))  # snout
    elif re.search(r"well|井", p):
        draw.ellipse((cx - 90, cy + 20, cx + 90, cy + 140), fill=(120, 115, 110))
        draw.ellipse((cx - 60, cy + 40, cx + 60, cy + 110), fill=(40, 50, 60))
        draw.rectangle((cx - 70, cy - 80, cx - 55, cy + 40), fill=wood)
        draw.rectangle((cx + 55, cy - 80, cx + 70, cy + 40), fill=wood)
        draw.rectangle((cx - 75, cy - 95, cx + 75, cy - 75), fill=wood)
    else:
        # wine jar / generic vessel with depth
        draw.ellipse((cx - 70, cy + 80, cx + 70, cy + 140), fill=wood)
        draw.polygon([(cx - 55, cy - 40), (cx + 55, cy - 40), (cx + 70, cy + 100), (cx - 70, cy + 100)], fill=roof)
        draw.ellipse((cx - 55, cy - 60, cx + 55, cy - 20), fill=(max(roof[0] - 20, 40), max(roof[1] - 10, 30), 30))
        draw.ellipse((cx - 25, cy - 80, cx + 25, cy - 50), fill=wood)


def _draw_character(draw: ImageDraw.ImageDraw, size: int, prompt: str) -> None:
    """Full-body Tang/Chang'an clothed figure — volumetric silhouette for Hunyuan3D."""
    p = prompt.lower()
    skin = (232, 196, 160)
    hair = (20, 18, 22)
    if re.search(r"scholar|书生|学|clerk|吏", p):
        robe, sash = (45, 70, 120), (200, 180, 80)
    elif re.search(r"guard|卫|镖|兵|archer|弓", p):
        robe, sash = (70, 55, 45), (140, 40, 35)
    elif re.search(r"farmer|农|beggar|丐|drunk|醉", p):
        robe, sash = (120, 100, 70), (90, 70, 45)
    elif re.search(r"trader|merchant|商|贩|摊|vendor", p):
        robe, sash = (160, 50, 45), (40, 90, 70)
    else:
        robe, sash = (55, 80, 95), (180, 140, 60)

    cx, cy = size // 2, size // 2 + 20
    # ground shadow (depth cue)
    draw.ellipse((cx - 70, cy + 175, cx + 70, cy + 205), fill=(230, 230, 230))
    # legs / boots under robe hem
    draw.rounded_rectangle((cx - 38, cy + 110, cx - 8, cy + 190), radius=10, fill=(50, 40, 35))
    draw.rounded_rectangle((cx + 8, cy + 110, cx + 38, cy + 190), radius=10, fill=(50, 40, 35))
    # robe body with side depth
    draw.polygon(
        [(cx - 75, cy - 40), (cx + 55, cy - 40), (cx + 85, cy + 130), (cx - 95, cy + 130)],
        fill=robe,
    )
    draw.polygon(
        [(cx + 55, cy - 40), (cx + 95, cy - 55), (cx + 115, cy + 110), (cx + 85, cy + 130)],
        fill=tuple(max(0, c - 25) for c in robe),
    )
    # sleeves
    draw.polygon([(cx - 75, cy - 20), (cx - 120, cy + 40), (cx - 95, cy + 70), (cx - 55, cy + 30)], fill=robe)
    draw.polygon([(cx + 55, cy - 20), (cx + 110, cy + 35), (cx + 95, cy + 65), (cx + 45, cy + 30)], fill=robe)
    # sash
    draw.rectangle((cx - 70, cy + 35, cx + 70, cy + 55), fill=sash)
    # collar
    draw.polygon([(cx - 25, cy - 40), (cx + 25, cy - 40), (cx, cy + 10)], fill=(245, 240, 230))
    # head + hair topknot
    draw.ellipse((cx - 42, cy - 130, cx + 42, cy - 45), fill=skin)
    draw.ellipse((cx - 48, cy - 145, cx + 48, cy - 85), fill=hair)
    draw.ellipse((cx - 18, cy - 175, cx + 18, cy - 135), fill=hair)
    # face accents
    draw.ellipse((cx - 18, cy - 100, cx - 8, cy - 90), fill=(40, 30, 25))
    draw.ellipse((cx + 8, cy - 100, cx + 18, cy - 90), fill=(40, 30, 25))
    if re.search(r"guard|卫|镖", p):
        # simple armor plate
        draw.rectangle((cx - 50, cy - 30, cx + 50, cy + 20), fill=(90, 85, 80), outline=(50, 45, 40), width=2)


def render_reference_png(prompt: str, *, kind: str = "character", size: int = 512) -> bytes:
    """Front / 3⁄4 reference on white — shaped for Hunyuan3D volume reconstruction."""
    bg = (255, 255, 255)
    img = Image.new("RGB", (size, size), bg)
    draw = ImageDraw.Draw(img)
    k = (kind or "prop").lower()
    pl = prompt.lower()

    if k == "building" or re.search(r"palace|temple|house|tavern|殿|楼|观|屋|宅|坊", pl):
        _draw_building(draw, size, prompt)
    elif k == "stall" or re.search(r"stall|摊|awning|棚", pl):
        _draw_stall(draw, size, prompt)
    elif k == "character":
        _draw_character(draw, size, prompt)
    else:
        _draw_prop(draw, size, prompt)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
