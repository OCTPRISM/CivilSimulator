#!/usr/bin/env python3
"""Ancient civ asset pack v2 — landmarks, residential/farmhouse variants, street props.

Writes GLBs under frontend/public/models/buildings/ancient/ and
frontend/public/models/props/ancient/.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_architecture_kits import Mesh  # noqa: E402

OUT_BLD = ROOT / "frontend/public/models/buildings/ancient"
OUT_PROP = ROOT / "frontend/public/models/props/ancient"

# Tang-ish palette
WALL = (0.93, 0.90, 0.84)
WOOD = (0.32, 0.22, 0.16)
ROOF = (0.55, 0.10, 0.12)
STONE = (0.58, 0.55, 0.50)
GOLD = (0.72, 0.52, 0.18)
THATCH = (0.62, 0.52, 0.28)
CLAY = (0.72, 0.58, 0.42)
INK = (0.18, 0.14, 0.12)
BANNER = (0.72, 0.12, 0.12)
LIT = (0.95, 0.85, 0.45)


def _posts(m: Mesh, bw: float, bd: float, bh: float, thick=0.28, rgb=WOOD):
    for sx in (-1, 1):
        for sz in (-1, 1):
            m.box(sx * bw * 0.42, bh / 2, sz * bd * 0.42, thick, bh, thick, rgb)


def _door_windows(m: Mesh, bw: float, bd: float, *, door_w=0.9, lit=LIT):
    m.box(0, 0.85, bd * 0.42, door_w, 1.7, 0.12, INK)
    m.box(-bw * 0.22, 1.45, bd * 0.42, 0.7, 0.85, 0.08, lit)
    m.box(bw * 0.22, 1.45, bd * 0.42, 0.7, 0.85, 0.08, lit)


def residential_variant(path: Path, variant: str):
    """Distinct silhouettes for town houses."""
    m = Mesh()
    cfg = {
        "a": dict(bw=3.8, bd=3.3, bh=2.6, layers=1, wing=False, porch=True, sign=False),
        "b": dict(bw=4.2, bd=3.0, bh=2.8, layers=1, wing=True, porch=False, sign=False),
        "c": dict(bw=3.5, bd=3.6, bh=2.5, layers=2, wing=False, porch=True, sign=False),
        "d": dict(bw=4.6, bd=3.4, bh=2.7, layers=1, wing=True, porch=True, sign=True),
        "e": dict(bw=3.2, bd=2.8, bh=2.4, layers=1, wing=False, porch=False, sign=False),
        "f": dict(bw=4.0, bd=4.0, bh=2.9, layers=2, wing=False, porch=True, sign=True),
    }[variant]
    bw, bd, bh = cfg["bw"], cfg["bd"], cfg["bh"]
    m.box(0, 0.05, bd * 0.52, bw * 0.3, 0.1, 0.35, STONE)
    _posts(m, bw, bd, bh)
    m.box(0, bh / 2, 0, bw * 0.82, bh, bd * 0.82, WALL)
    m.box(0, bh + 0.08, 0, bw * 0.95, 0.16, bd * 0.95, WOOD)
    _door_windows(m, bw, bd)
    if cfg["wing"]:
        m.box(bw * 0.55, bh * 0.4, 0, bw * 0.35, bh * 0.75, bd * 0.55, WALL)
        m.hip_roof(bw * 0.55, bh * 0.78, 0, bw * 0.42, bd * 0.65, 0.55, ROOF, WOOD)
    if cfg["porch"]:
        m.box(0, 1.1, bd * 0.55, bw * 0.55, 0.12, 0.7, WOOD)
        m.box(-bw * 0.22, 0.55, bd * 0.55, 0.12, 1.1, 0.12, WOOD)
        m.box(bw * 0.22, 0.55, bd * 0.55, 0.12, 1.1, 0.12, WOOD)
    if cfg["sign"]:
        m.box(0, bh * 0.7, bd * 0.48, 1.6, 0.35, 0.08, BANNER)
    for i in range(cfg["layers"]):
        scale = 1.15 + (cfg["layers"] - i) * 0.1
        y = bh + 0.15 + i * 0.85
        m.hip_roof(0, y, 0, bw * scale, bd * scale, 0.75, ROOF, WOOD)
    m.save(path)


def farmhouse_variant(path: Path, variant: str):
    """Low thatch / clay rural houses — visibly different from town homes."""
    m = Mesh()
    cfg = {
        "a": dict(bw=3.4, bd=2.8, bh=2.1, thatch=True, lean_to=False),
        "b": dict(bw=4.0, bd=3.0, bh=2.2, thatch=True, lean_to=True),
        "c": dict(bw=3.0, bd=3.2, bh=2.0, thatch=False, lean_to=True),
        "d": dict(bw=3.6, bd=2.6, bh=2.15, thatch=True, lean_to=False),
    }[variant]
    bw, bd, bh = cfg["bw"], cfg["bd"], cfg["bh"]
    wall = CLAY if cfg["thatch"] else (0.88, 0.82, 0.70)
    roof = THATCH if cfg["thatch"] else ROOF
    m.box(0, 0.04, 0, bw * 1.05, 0.08, bd * 1.05, STONE)
    _posts(m, bw, bd, bh, thick=0.22, rgb=(0.28, 0.20, 0.12))
    m.box(0, bh / 2, 0, bw * 0.88, bh, bd * 0.88, wall)
    m.box(0, 0.75, bd * 0.45, 0.75, 1.5, 0.1, INK)
    m.box(-bw * 0.2, 1.2, bd * 0.45, 0.55, 0.65, 0.06, (0.35, 0.28, 0.18))
    # steep thatch / simple hip
    m.hip_roof(0, bh + 0.05, 0, bw * 1.25, bd * 1.25, 1.15 if cfg["thatch"] else 0.7, roof, WOOD)
    if cfg["lean_to"]:
        m.box(-bw * 0.55, bh * 0.35, 0, bw * 0.4, bh * 0.65, bd * 0.7, wall)
        m.hip_roof(-bw * 0.55, bh * 0.7, 0, bw * 0.5, bd * 0.85, 0.55, roof, WOOD)
    # hay stack / fence post accent
    m.box(bw * 0.55, 0.45, bd * 0.35, 0.7, 0.9, 0.7, THATCH)
    m.save(path)


def landmark_tavern(path: Path):
    """醉仙楼 — two-storey wine house with banner poles and balcony."""
    m = Mesh()
    bw, bd, bh = 6.4, 5.2, 3.2
    m.box(0, 0.08, bd * 0.55, bw * 0.4, 0.16, 0.55, STONE)
    _posts(m, bw, bd, bh * 2.05, thick=0.32)
    # ground hall
    m.box(0, bh / 2, 0, bw * 0.88, bh, bd * 0.88, WALL)
    m.box(0, bh + 0.1, 0, bw * 1.0, 0.2, bd * 1.0, WOOD)
    # upper storey set back slightly
    m.box(0, bh + 1.55, 0, bw * 0.78, 2.8, bd * 0.78, WALL)
    m.box(0, bh + 3.05, 0, bw * 0.9, 0.18, bd * 0.9, WOOD)
    # balcony
    m.box(0, bh + 0.35, bd * 0.48, bw * 0.7, 0.12, 0.9, WOOD)
    for sx in (-1, 0, 1):
        m.box(sx * bw * 0.28, bh + 0.9, bd * 0.55, 0.08, 1.1, 0.08, WOOD)
    # multi eaves
    m.hip_roof(0, bh + 0.25, 0, bw * 1.25, bd * 1.2, 0.9, ROOF, WOOD)
    m.hip_roof(0, bh + 3.2, 0, bw * 1.05, bd * 1.0, 1.05, ROOF, WOOD)
    m.box(0, bh + 4.4, 0, 0.35, 0.35, 0.35, GOLD)
    # wine banners
    for sx in (-1, 1):
        m.box(sx * bw * 0.55, bh * 0.9, bd * 0.52, 0.12, bh * 1.4, 0.12, WOOD)
        m.box(sx * bw * 0.55, bh * 1.35, bd * 0.58, 0.55, 1.2, 0.06, BANNER)
    # shop front
    m.box(0, 1.0, bd * 0.45, 1.2, 2.0, 0.14, INK)
    m.box(0, bh * 0.65, bd * 0.5, 2.8, 0.5, 0.1, (0.55, 0.12, 0.1))
    m.box(-bw * 0.25, 1.55, bd * 0.45, 0.85, 1.0, 0.08, LIT)
    m.box(bw * 0.25, 1.55, bd * 0.45, 0.85, 1.0, 0.08, LIT)
    m.save(path)


def landmark_palace(path: Path):
    """紫宸殿 — raised platform, triple eaves, gold ridge ornaments."""
    m = Mesh()
    bw, bd, bh = 8.5, 6.8, 3.6
    # stone platform + steps
    m.box(0, 0.35, 0, bw * 1.15, 0.7, bd * 1.15, STONE)
    m.box(0, 0.15, bd * 0.7, bw * 0.35, 0.3, 1.2, STONE)
    _posts(m, bw, bd, bh, thick=0.38, rgb=(0.28, 0.18, 0.12))
    m.box(0, bh / 2 + 0.35, 0, bw * 0.85, bh, bd * 0.85, WALL)
    m.box(0, bh + 0.45, 0, bw * 0.98, 0.22, bd * 0.98, WOOD)
    # vermilion doors
    m.box(-0.7, 1.4, bd * 0.44, 1.1, 2.4, 0.14, BANNER)
    m.box(0.7, 1.4, bd * 0.44, 1.1, 2.4, 0.14, BANNER)
    for sx in (-1.6, 1.6):
        m.box(sx, 2.0, bd * 0.44, 0.9, 1.1, 0.08, LIT)
    # triple eaves
    for i, (sc, hy) in enumerate([(1.35, 0.0), (1.2, 1.15), (1.05, 2.2)]):
        y = bh + 0.55 + hy
        m.hip_roof(0, y, 0, bw * sc, bd * sc, 1.05, ROOF, WOOD)
        m.box(0, y + 1.15, 0, 0.3, 0.3, 0.3, GOLD)
    # side galleries
    for sx in (-1, 1):
        m.box(sx * bw * 0.62, bh * 0.45, 0, bw * 0.28, bh * 0.7, bd * 0.7, WALL)
        m.hip_roof(sx * bw * 0.62, bh * 0.85, 0, bw * 0.38, bd * 0.85, 0.7, ROOF, WOOD)
    m.save(path)


def landmark_temple(path: Path):
    """终南古观 — mountain Daoist temple with incense burner & stone lanterns."""
    m = Mesh()
    bw, bd, bh = 5.8, 5.0, 2.9
    m.box(0, 0.12, 0, bw * 1.1, 0.24, bd * 1.1, STONE)
    _posts(m, bw, bd, bh, thick=0.3, rgb=(0.25, 0.18, 0.12))
    m.box(0, bh / 2, 0, bw * 0.82, bh, bd * 0.82, (0.9, 0.88, 0.82))
    m.box(0, bh + 0.1, 0, bw * 0.95, 0.18, bd * 0.95, WOOD)
    m.box(0, 0.95, bd * 0.42, 1.0, 1.9, 0.12, INK)
    # circular moon gate suggestion on side
    m.box(-bw * 0.42, 1.4, 0, 0.12, 1.6, 1.4, WOOD)
    for i in range(2):
        scale = 1.28 - i * 0.14
        y = bh + 0.2 + i * 1.05
        m.hip_roof(0, y, 0, bw * scale, bd * scale, 0.95, (0.42, 0.12, 0.14), WOOD)
        m.box(0, y + 1.05, 0, 0.28, 0.28, 0.28, GOLD)
    # incense burner in front
    m.box(0, 0.55, bd * 0.7, 0.9, 0.7, 0.9, STONE)
    m.box(0, 1.05, bd * 0.7, 0.55, 0.25, 0.55, (0.35, 0.32, 0.28))
    # stone lanterns
    for sx in (-1, 1):
        m.box(sx * bw * 0.45, 0.7, bd * 0.65, 0.35, 1.4, 0.35, STONE)
        m.box(sx * bw * 0.45, 1.5, bd * 0.65, 0.5, 0.35, 0.5, LIT)
    m.save(path)


# ---- Street props ----

def prop_lantern(path: Path):
    m = Mesh()
    m.box(0, 1.1, 0, 0.12, 2.2, 0.12, WOOD)
    m.box(0, 2.35, 0, 0.55, 0.7, 0.55, LIT)
    m.box(0, 2.75, 0, 0.35, 0.12, 0.35, WOOD)
    m.save(path)


def prop_banner(path: Path):
    m = Mesh()
    m.box(0, 1.4, 0, 0.1, 2.8, 0.1, WOOD)
    m.box(0.35, 1.8, 0, 0.7, 1.4, 0.05, BANNER)
    m.save(path)


def prop_table(path: Path):
    m = Mesh()
    m.box(0, 0.72, 0, 1.2, 0.08, 0.8, WOOD)
    for sx, sz in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        m.box(sx * 0.45, 0.36, sz * 0.28, 0.1, 0.72, 0.1, WOOD)
    m.save(path)


def prop_stool(path: Path):
    m = Mesh()
    m.box(0, 0.42, 0, 0.45, 0.08, 0.45, WOOD)
    m.box(0, 0.2, 0, 0.12, 0.4, 0.12, WOOD)
    m.save(path)


def prop_well(path: Path):
    m = Mesh()
    m.box(0, 0.45, 0, 1.4, 0.9, 1.4, STONE)
    m.box(0, 0.95, 0, 1.0, 0.15, 1.0, WOOD)
    m.box(-0.55, 1.4, 0, 0.1, 0.9, 0.1, WOOD)
    m.box(0.55, 1.4, 0, 0.1, 0.9, 0.1, WOOD)
    m.box(0, 1.85, 0, 1.3, 0.1, 0.1, WOOD)
    m.save(path)


def prop_stone_lion(path: Path):
    m = Mesh()
    m.box(0, 0.25, 0, 0.7, 0.5, 0.7, STONE)
    m.box(0, 0.75, 0, 0.55, 0.55, 0.45, STONE)
    m.box(0, 1.15, 0.1, 0.4, 0.35, 0.4, STONE)
    m.save(path)


def prop_crate(path: Path):
    m = Mesh()
    m.box(0, 0.35, 0, 0.7, 0.7, 0.7, WOOD)
    m.save(path)


def prop_wine_jar(path: Path):
    m = Mesh()
    m.box(0, 0.4, 0, 0.55, 0.8, 0.55, CLAY)
    m.box(0, 0.85, 0, 0.35, 0.2, 0.35, CLAY)
    m.save(path)


def prop_bench(path: Path):
    m = Mesh()
    m.box(0, 0.4, 0, 1.4, 0.1, 0.4, STONE)
    m.box(-0.55, 0.2, 0, 0.15, 0.4, 0.35, STONE)
    m.box(0.55, 0.2, 0, 0.15, 0.4, 0.35, STONE)
    m.save(path)


def prop_flower_pot(path: Path):
    m = Mesh()
    m.box(0, 0.25, 0, 0.4, 0.5, 0.4, CLAY)
    m.box(0, 0.6, 0, 0.35, 0.35, 0.35, (0.25, 0.45, 0.22))
    m.save(path)


def prop_cart(path: Path):
    m = Mesh()
    m.box(0, 0.55, 0, 1.6, 0.7, 0.9, WOOD)
    m.box(-0.7, 0.35, 0.55, 0.15, 0.7, 0.15, WOOD)
    m.box(0.7, 0.35, 0.55, 0.15, 0.7, 0.15, WOOD)
    m.box(-0.7, 0.35, -0.55, 0.15, 0.7, 0.15, WOOD)
    m.box(0.7, 0.35, -0.55, 0.15, 0.7, 0.15, WOOD)
    m.save(path)


def main():
    OUT_BLD.mkdir(parents=True, exist_ok=True)
    OUT_PROP.mkdir(parents=True, exist_ok=True)

    for v in "abcdef":
        residential_variant(OUT_BLD / f"residential_{v}.glb", v)
    for v in "abcd":
        farmhouse_variant(OUT_BLD / f"farmhouse_{v}.glb", v)

    landmark_tavern(OUT_BLD / "landmark_tavern.glb")
    landmark_palace(OUT_BLD / "landmark_palace.glb")
    landmark_temple(OUT_BLD / "landmark_temple.glb")

    # Keep tower/gate distinct (reuse gate if present; refresh tower silhouette)
    m = Mesh()
    _posts(m, 3.6, 3.6, 5.2, thick=0.32)
    m.box(0, 2.6, 0, 3.0, 5.2, 3.0, WALL)
    m.hip_roof(0, 5.4, 0, 4.2, 4.2, 1.0, ROOF, WOOD)
    m.hip_roof(0, 6.5, 0, 3.4, 3.4, 0.85, ROOF, WOOD)
    m.box(0, 1.2, 1.55, 1.0, 2.2, 0.15, INK)
    m.save(OUT_BLD / "tower_a.glb")
    m.save(OUT_BLD / "tower_b.glb")

    props = {
        "lantern": prop_lantern,
        "banner": prop_banner,
        "table": prop_table,
        "stool": prop_stool,
        "well": prop_well,
        "stone_lion": prop_stone_lion,
        "crate": prop_crate,
        "wine_jar": prop_wine_jar,
        "bench": prop_bench,
        "flower_pot": prop_flower_pot,
        "cart": prop_cart,
    }
    for name, fn in props.items():
        fn(OUT_PROP / f"{name}.glb")

    print("ancient assets v2:")
    print("  buildings", sorted(p.name for p in OUT_BLD.glob("*.glb")))
    print("  props", sorted(p.name for p in OUT_PROP.glob("*.glb")))


if __name__ == "__main__":
    main()
