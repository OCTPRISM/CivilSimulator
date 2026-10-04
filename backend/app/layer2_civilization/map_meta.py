"""Load frontend map JSON for backend agent positioning."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_MAP_ROOT = Path(__file__).resolve().parents[3] / "frontend" / "public" / "maps"


@lru_cache(maxsize=8)
def load_map_meta(genre: str) -> dict:
    p = _MAP_ROOT / f"{genre}.json"
    if not p.exists():
        return {"width": 960, "height": 540, "locations": [], "terrain": {}}
    return json.loads(p.read_text(encoding="utf-8"))


def loc_coords(genre: str, location_name: str) -> tuple[float, float] | None:
    m = load_map_meta(genre)
    w, h = m.get("width", 960), m.get("height", 540)
    for loc in m.get("locations") or []:
        if loc.get("name") == location_name:
            return _px_to_norm(loc["x"], loc["y"], w, h)
    return None


def loc_id_coords(genre: str, world, location_id: str | None) -> tuple[float, float]:
    if not location_id or location_id not in world.locations:
        return 0.0, 0.0
    name = world.locations[location_id].name
    c = loc_coords(genre, name)
    if c:
        return c
    # fallback hash
    h = sum(ord(c) for c in location_id) % 1000
    return (h / 500 - 1) * 0.3, ((h * 7) % 1000 / 500 - 1) * 0.3


def _px_to_norm(x: float, y: float, w: float, h: float) -> tuple[float, float]:
    return (x / w - 0.5) * 2.0, (y / h - 0.5) * 2.0


def _norm_to_px(nx: float, nz: float, w: float, h: float) -> tuple[float, float]:
    return (nx * 0.5 + 0.5) * w, (nz * 0.5 + 0.5) * h


def snap_norm_to_road(
    genre: str,
    nx: float,
    nz: float,
    *,
    along: float = 0.0,
    side: float = 0.0,
) -> tuple[float, float]:
    """Project normalized world coords onto nearest road centerline.

    `along` shifts along the segment tangent (norm-space approx via px).
    `side` is lateral offset in map pixels (keep small so agents stay on strip).
    """
    m = load_map_meta(genre)
    roads = m.get("roads") or []
    if not roads:
        return nx, nz
    w, h = float(m.get("width", 960)), float(m.get("height", 540))
    px, py = _norm_to_px(nx, nz, w, h)
    best_d = 1e18
    best = (px, py)
    best_tan = (1.0, 0.0)
    best_n = (0.0, 1.0)
    for r in roads:
        ax, ay = r["from"]
        bx, by = r["to"]
        abx, aby = bx - ax, by - ay
        ab2 = abx * abx + aby * aby or 1.0
        t = max(0.0, min(1.0, ((px - ax) * abx + (py - ay) * aby) / ab2))
        qx, qy = ax + abx * t, ay + aby * t
        d = (px - qx) ** 2 + (py - qy) ** 2
        if d < best_d:
            best_d = d
            length = ab2 ** 0.5
            tx, ty = abx / length, aby / length
            best_tan = (tx, ty)
            best_n = (-ty, tx)
            best = (qx, qy)
    qx = best[0] + best_tan[0] * along + best_n[0] * side
    qy = best[1] + best_tan[1] * along + best_n[1] * side
    return _px_to_norm(qx, qy, w, h)
