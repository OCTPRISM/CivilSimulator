#!/usr/bin/env python3
"""Build civilization maps from map_briefs_v2 distance specs (no legacy DNA).

Usage:
  python3 backend/scripts/build_map_v2.py --civ ancient
  python3 backend/scripts/build_map_v2.py --civ ancient --dit
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

BRIEF = ROOT / "backend/app/generator/map_briefs_v2/civilization_map_prompts.json"
OUT_MAPS = ROOT / "frontend/public/maps"
CIV_ROOT = ROOT / "frontend/public/models/characters/civilizations"
RUNTIME = ROOT / "backend/data/runtime/generator/maps"
VENV_PY = ROOT / "backend/.venv-hunyuan3d/bin/python3"
T2I_CLI = ROOT / "backend/scripts/hunyuan3d/text_to_image_cli.py"

# Map canvas — taller to fit N–S ancient corridor
W, H = 960, 1200


def load_brief(civ: str) -> dict:
    data = json.loads(BRIEF.read_text(encoding="utf-8"))
    if civ not in data["civilizations"]:
        raise SystemExit(f"unknown civ {civ}")
    return data["civilizations"][civ]


def meter_bounds(anchors: dict) -> tuple[float, float, float, float]:
    xs, ys = [], []
    for a in anchors.values():
        if "xy_m" in a:
            xs.append(float(a["xy_m"][0]))
            ys.append(float(a["xy_m"][1]))
    pad = 160.0
    return min(xs) - pad, max(xs) + pad, min(ys) - pad, max(ys) + pad


def make_projectors(anchors: dict):
    xmin, xmax, ymin, ymax = meter_bounds(anchors)
    span_x = xmax - xmin
    span_y = ymax - ymin

    def m2p(x: float, y: float) -> tuple[float, float]:
        # +Y north → smaller map-y (north at top of image)
        px = (x - xmin) / span_x * (W - 40) + 20
        py = (ymax - y) / span_y * (H - 40) + 20
        return px, py

    # Relative layout is authoritative; compress absolute scale for readable playable density.
    # Full meter fidelity remains in distanceAudit / bounds_m.
    world_scale = min(1.45, span_x / (0.38 * W))
    return m2p, world_scale, (xmin, xmax, ymin, ymax, span_x, span_y)


def road(a, b, kind="dirt"):
    return {
        "from": [round(a[0], 1), round(a[1], 1)],
        "to": [round(b[0], 1), round(b[1], 1)],
        "kind": kind,
    }


def building(**kw):
    kw.setdefault("enterable", False)
    kw.setdefault("floors", 1)
    kw.setdefault("rot", 0)
    return kw


def _seg_dist(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    abx, aby = bx - ax, by - ay
    apx, apy = px - ax, py - ay
    ab2 = abx * abx + aby * aby or 1.0
    t = max(0.0, min(1.0, (apx * abx + apy * aby) / ab2))
    return math.hypot(px - (ax + t * abx), py - (ay + t * aby))


def _road_dist(px: float, py: float, roads: list[dict]) -> float:
    return min((_seg_dist(px, py, *r["from"], *r["to"]) for r in roads), default=1e9)


def _in_water(px: float, py: float, water: list[dict], rivers: list[dict], margin: float = 6.0) -> bool:
    for w in water:
        dx = (px - w["x"]) / max(w["rx"] + margin, 1)
        dy = (py - w["y"]) / max(w["ry"] + margin, 1)
        if dx * dx + dy * dy <= 1.0:
            return True
    for rv in rivers:
        half = (rv.get("width") or 20) * 0.5 + margin
        pts = rv["points"]
        for i in range(len(pts) - 1):
            if _seg_dist(px, py, *pts[i], *pts[i + 1]) < half:
                return True
    return False


def _aabb_overlap(
    ax: float, ay: float, aw: float, ah: float,
    bx: float, by: float, bw: float, bh: float,
    pad: float = 4.0,
) -> bool:
    """True if axis-aligned footprints collide (with padding gap)."""
    return not (
        ax + aw + pad <= bx
        or bx + bw + pad <= ax
        or ay + ah + pad <= by
        or by + bh + pad <= ay
    )


def _footprint_ok(
    x: float, y: float, w: float, h: float,
    roads: list[dict], water: list[dict], rivers: list[dict],
    occupied: list[tuple[float, float, float, float]],
    *,
    allow_on_road: bool = False,
    allow_in_water: bool = False,
    road_half: float = 7.0,
    road_clear: float = 2.5,
    curb_min: float | None = 11.0,
    curb_max: float | None = 42.0,
    pad: float = 4.0,
) -> bool:
    """Reject road carriageway / water unless allowed. Optional curb band for street fill.

    Occupancy uses AABB (not circles) so stalls cannot nest inside shop footprints.
    Road clearance is measured from the nearest footprint corner (not just center).
    """
    cx, cy = x + w * 0.5, y + h * 0.5
    if any(_aabb_overlap(x, y, w, h, ox, oy, ow, oh, pad=pad) for ox, oy, ow, oh in occupied):
        return False
    corners = ((x, y), (x + w, y), (x, y + h), (x + w, y + h), (cx, cy))
    if not allow_in_water:
        for qx, qy in corners:
            if _in_water(qx, qy, water, rivers, margin=5.0):
                return False
    # Nearest distance from any footprint sample to road centerline
    d_edge = min(_road_dist(qx, qy, roads) for qx, qy in corners)
    d_center = _road_dist(cx, cy, roads)
    if allow_on_road:
        return d_center <= road_half + 4
    # Carriageway keep-clear: footprint must stay outside asphalt band
    if not allow_in_water and d_edge < road_half + road_clear:
        return False
    if curb_min is not None and d_center < curb_min:
        return False
    if curb_max is not None and d_center > curb_max:
        return False
    return True


def _try_add(
    buildings: list[dict], occupied: list,
    roads, water, rivers, *,
    allow_on_road=False, allow_in_water=False,
    curb_min: float | None = 11.0, curb_max: float | None = 42.0,
    search: bool = False,
    zone: str | None = None,
    pad: float = 4.0,
    road_half: float = 7.0,
    road_clear: float = 2.5,
    **kw,
) -> bool:
    """Try exact spot; if search=True spiral until hard rules pass (landmarks)."""
    w, h = kw["w"], kw["h"]
    ox0, oy0 = float(kw["x"]), float(kw["y"])
    candidates = [(0.0, 0.0)]
    if search:
        for ring in range(1, 20):
            step = 6.0 * ring
            for ang in range(0, 360, 24):
                rad = math.radians(ang)
                candidates.append((math.cos(rad) * step, math.sin(rad) * step))
    band_passes = (
        [(curb_min, curb_max), (9.0, None), (None, None)] if search else [(curb_min, curb_max)]
    )
    for dx, dy in candidates:
        x, y = ox0 + dx, oy0 + dy
        for cmin, cmax in band_passes:
            if not _footprint_ok(
                x, y, w, h, roads, water, rivers, occupied,
                allow_on_road=allow_on_road, allow_in_water=allow_in_water,
                curb_min=cmin, curb_max=cmax, pad=pad,
                road_half=road_half, road_clear=road_clear,
            ):
                continue
            payload = {**kw, "x": round(x, 1), "y": round(y, 1)}
            if zone:
                payload["zone"] = zone
            buildings.append(building(**payload))
            occupied.append((x, y, w, h))
            return True
    return False


def _face_road_yaw(side: float, nx: float, ny: float) -> float:
    """Yaw so local +Z (door/front) faces the roadway."""
    return math.atan2(-side * nx, -side * ny)


def _yaw_face_point(cx: float, cy: float, tx: float, ty: float) -> float:
    """Three.js Y-yaw: local +Z maps to (sin, cos) in map (x, y)."""
    return math.atan2(tx - cx, ty - cy)


def _closest_on_seg(
    px: float, py: float, ax: float, ay: float, bx: float, by: float,
) -> tuple[float, float]:
    abx, aby = bx - ax, by - ay
    ab2 = abx * abx + aby * aby or 1.0
    t = max(0.0, min(1.0, ((px - ax) * abx + (py - ay) * aby) / ab2))
    return ax + t * abx, ay + t * aby


def _place_landmark_facing_road(
    buildings, occupied, roads, water, rivers,
    a, b, *, t: float, side: int, setback: float, w: float, h: float,
    pad: float = 4.0, **kw,
) -> bool:
    """Place a primary landmark on the curb; door (+Z) aims at the intended street.

    Setback is distance from road centerline to the FRONT FACE (not center),
    so the gate sits on a short porch opening onto the street.
    """
    ax, ay = a
    bx, by = b
    length = math.hypot(bx - ax, by - ay) or 1.0
    dx, dy = (bx - ax) / length, (by - ay) / length
    nx, ny = -dy, dx
    # Depth along the normal (front→back). Door faces along ±normal.
    # After yaw, map footprint is still AABB: depth contribution ≈ h/2 when
    # facing N/S (rot~0/π), w/2 when facing E/W (rot~±π/2). Use max for clearance.
    depth_half = max(w, h) * 0.5
    # Front face ~ road_half(7) + porch(3) from centerline
    face_gap = 10.0
    base_sb = max(setback, face_gap + depth_half)
    # Allow front face close to carriageway edge
    lm_clear = 0.6
    lm_half = 7.0
    for dt in (0.0, 0.04, -0.04, 0.08, -0.08, 0.12, -0.12, 0.18):
        for sb in (base_sb, base_sb + 3, base_sb + 6, base_sb - 2, base_sb + 10):
            if sb < face_gap + 8:
                continue
            tt = min(0.85, max(0.15, t + dt))
            cx = ax + (bx - ax) * tt
            cy = ay + (by - ay) * tt
            # Center sits setback along normal; front face ≈ sb - depth_half from road
            fcx = cx + nx * sb * side
            fcy = cy + ny * sb * side
            px = fcx - w * 0.5
            py = fcy - h * 0.5
            yaw = _yaw_face_point(fcx, fcy, cx, cy)
            n_before = len(buildings)
            if _try_add(
                buildings, occupied, roads, water, rivers,
                x=round(px, 1), y=round(py, 1), w=w, h=h,
                rot=round(yaw, 3),
                curb_min=face_gap, curb_max=55.0, search=False, pad=pad,
                road_half=lm_half, road_clear=lm_clear,
                **kw,
            ):
                bld = buildings[-1]
                bcx = bld["x"] + bld["w"] * 0.5
                bcy = bld["y"] + bld["h"] * 0.5
                rx, ry = _closest_on_seg(bcx, bcy, ax, ay, bx, by)
                bld["rot"] = round(_yaw_face_point(bcx, bcy, rx, ry), 3)
                return True
            assert len(buildings) == n_before
    # Spiral fallback — still re-aim at THIS segment
    cx = ax + (bx - ax) * t
    cy = ay + (by - ay) * t
    fcx = cx + nx * base_sb * side
    fcy = cy + ny * base_sb * side
    yaw = _yaw_face_point(fcx, fcy, cx, cy)
    ok = _try_add(
        buildings, occupied, roads, water, rivers,
        x=round(fcx - w * 0.5, 1), y=round(fcy - h * 0.5, 1), w=w, h=h,
        rot=round(yaw, 3),
        curb_min=face_gap, curb_max=70.0, search=True, pad=pad,
        road_half=lm_half, road_clear=lm_clear,
        **kw,
    )
    if ok:
        bld = buildings[-1]
        bcx = bld["x"] + bld["w"] * 0.5
        bcy = bld["y"] + bld["h"] * 0.5
        rx, ry = _closest_on_seg(bcx, bcy, ax, ay, bx, by)
        bld["rot"] = round(_yaw_face_point(bcx, bcy, rx, ry), 3)
    return ok


def _place_along_road(
    buildings, occupied, roads, water, rivers, rng,
    a, b, *, sides, setback, spacing, city, urban: bool, zone: str,
):
    """Place buildings in curb strip along segment a→b, fronts facing the street."""
    ax, ay = a
    bx, by = b
    length = math.hypot(bx - ax, by - ay) or 1.0
    dx, dy = (bx - ax) / length, (by - ay) / length
    nx, ny = -dy, dx
    t = 0.06 if urban else 0.12
    t_end = 0.94 if urban else 0.88
    idx = 0
    while t < t_end:
        cx = ax + (bx - ax) * t
        cy = ay + (by - ay) * t
        for side in sides:
            if urban:
                fw = 14 + rng.randint(0, 8)
                fh = 12 + rng.randint(0, 6)
                floors = 2 if rng.random() < 0.4 else 1
                typ = "commercial" if rng.random() < 0.55 else "residential"
                sign = rng.choice(["商铺", "茶寮", "民居", "酒旗", "客栈", "米铺", "绸庄", "药铺"])
                sb = setback + rng.uniform(2, 6)
                cmin, cmax = 18.0, 48.0
            else:
                fw = 15 + rng.randint(0, 7)
                fh = 13 + rng.randint(0, 5)
                floors = 1
                typ = "farmhouse"
                sign = rng.choice(["田舍", "茅屋", "农家", "草屋"])
                sb = setback + rng.uniform(12, 28)
                cmin, cmax = 32.0, 100.0
            px = cx + nx * sb * side - fw * 0.5
            py = cy + ny * sb * side - fh * 0.5
            yaw = _face_road_yaw(side, nx, ny)
            _try_add(
                buildings, occupied, roads, water, rivers,
                name=f"{city}·{sign}·{idx}",
                x=round(px, 1), y=round(py, 1), w=fw, h=fh,
                floors=floors, type=typ, sign=sign, banner=urban, city=city,
                rot=round(yaw, 3),
                curb_min=cmin, curb_max=cmax, zone=zone,
            )
            idx += 1
        t += spacing * (0.85 + rng.random() * 0.3)


def _place_stall_on_street(
    buildings, occupied, roads, water, rivers,
    a, b, *, t: float, side: int, sign: str, city: str, zone: str = "urban",
) -> bool:
    """Place a named stall ON the curb, front flush to the street — no spiral search."""
    ax, ay = a
    bx, by = b
    length = math.hypot(bx - ax, by - ay) or 1.0
    dx, dy = (bx - ax) / length, (by - ay) / length
    nx, ny = -dy, dx
    fw, fh = 7.0, 5.5  # compact so footprint edges stay off carriageway
    yaw = _face_road_yaw(side, nx, ny)
    for dt in (0.0, 0.05, -0.05, 0.1, -0.1, 0.15, -0.15, 0.2, -0.2):
        tt = min(0.9, max(0.1, t + dt))
        cx = ax + (bx - ax) * tt
        cy = ay + (by - ay) * tt
        # Sit just outside carriageway (road_half≈7) so stalls hug the street edge
        # Inner curb: stall edge may sit just outside carriageway (road_half≈7)
        for sb in (11.5, 12.5, 10.5, 13.5, 14.5, 15.5):
            px = cx + nx * sb * side - fw * 0.5
            py = cy + ny * sb * side - fh * 0.5
            if _try_add(
                buildings, occupied, roads, water, rivers,
                name=f"西市摊·{sign}",
                x=round(px, 1), y=round(py, 1), w=fw, h=fh,
                floors=1, type="stall", sign=sign, city=city, zone=zone,
                rot=round(yaw, 3), stallKind=sign,
                curb_min=9.0, curb_max=17.0, search=False, pad=2.5,
                road_half=7.0, road_clear=0.4,
            ):
                return True
    return False


def _prune_orphan_roads(roads: list[dict], buildings: list[dict], *, keep_spine: set[tuple]) -> list[dict]:
    """Drop road segments that have no curb buildings (except spine arterials)."""
    kept = []
    for r in roads:
        key = (tuple(r["from"]), tuple(r["to"]))
        key_rev = (tuple(r["to"]), tuple(r["from"]))
        if key in keep_spine or key_rev in keep_spine:
            kept.append(r)
            continue
        n = 0
        for b in buildings:
            if b.get("type") in ("dock",):
                continue
            cx = b["x"] + b["w"] * 0.5
            cy = b["y"] + b["h"] * 0.5
            d = _seg_dist(cx, cy, *r["from"], *r["to"])
            if 8.0 <= d <= 48.0:
                n += 1
        if n >= 2:
            kept.append(r)
    return kept


def _orient_buildings_to_roads(buildings: list[dict], roads: list[dict]) -> None:
    """Ensure every non-gate building faces its nearest street."""
    for b in buildings:
        if b.get("type") in ("tower", "dock"):
            continue
        # Keep explicit yaw from street-facing landmark / stall placement
        if b.get("landmark") == "primary":
            continue
        if b.get("rot") is not None and b.get("type") == "stall":
            continue
        cx = b["x"] + b["w"] * 0.5
        cy = b["y"] + b["h"] * 0.5
        best = None
        best_d = 1e9
        for r in roads:
            ax, ay = r["from"]
            bx, by = r["to"]
            d = _seg_dist(cx, cy, ax, ay, bx, by)
            if d < best_d:
                best_d = d
                length = math.hypot(bx - ax, by - ay) or 1.0
                dx, dy = (bx - ax) / length, (by - ay) / length
                nx, ny = -dy, dx
                # which side is the building on?
                # vector from segment midpoint-ish projection to building
                abx, aby = bx - ax, by - ay
                apx, apy = cx - ax, cy - ay
                t = max(0.0, min(1.0, (apx * abx + apy * aby) / (abx * abx + aby * aby or 1)))
                px, py = ax + t * abx, ay + t * aby
                side = 1 if ((cx - px) * nx + (cy - py) * ny) >= 0 else -1
                best = _face_road_yaw(side, nx, ny)
        if best is not None:
            b["rot"] = round(best, 3)



def build_ancient(brief: dict) -> dict:
    dist = brief["spatial_logic"]["distances"]
    anchors = dist["anchors"]
    m2p, world_scale, bounds = make_projectors(anchors)
    xmin, xmax, ymin, ymax, span_x, span_y = bounds
    rng = random.Random(1201)

    A = m2p(*anchors["A_西市酒肆门楣"]["xy_m"])
    B = m2p(*anchors["B_紫宸殿外御道中心"]["xy_m"])
    C = m2p(*anchors["C_终南古观山门"]["xy_m"])
    Gate = m2p(*anchors["南门外瓮城"]["xy_m"])

    alley = m2p(120.0, 0.0)
    junction = m2p(420.0, 690.0)
    foothill = m2p(180.0, -780.0)
    # Pier direction hint (final pier coords recomputed on far bank past 渭水)
    pier_hint = m2p(-180.0, 60.0)

    cities = [
        {"name": "长安·西市酒肆", "x": round(A[0], 1), "y": round(A[1], 1), "r": 110},
        {"name": "大明宫·紫宸殿外", "x": round(B[0], 1), "y": round(B[1], 1), "r": 120},
        {"name": "终南山·古观", "x": round(C[0], 1), "y": round(C[1], 1), "r": 90},
    ]

    # ---- Roads / water / bridges ----
    # Four rays from A → proper T/X junctions; arterials leave from ray tips only.
    # CRITICAL: roads STOP at bridge abutments — never run through water under a span.
    m_w = m2p(-90, 0)
    m_e = m2p(90, 0)
    m_s = m2p(0, -85)
    m_n = m2p(0, 85)

    def _pt(a, b, t: float) -> list[float]:
        return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]

    # 渭水 / 护城河: water first, then cut roads so NOTHING runs under the bridge
    wei_rx, wei_ry = 38.0, 26.0
    moat_rx, moat_ry = 40.0, 14.0
    # Moat well south of 南门 so bridge approach never covers the gate doors
    moat_t = 0.22
    moat_len = math.hypot(foothill[0] - Gate[0], foothill[1] - Gate[1]) or 1.0
    moat_cx, moat_cy = _pt(Gate, foothill, moat_t)
    gate_ang = math.atan2(foothill[0] - Gate[0], foothill[1] - Gate[1])

    def _ellipse_half_along(ux: float, uy: float, rx: float, ry: float) -> float:
        q = (ux / max(rx, 1e-3)) ** 2 + (uy / max(ry, 1e-3)) ** 2
        return 1.12 / math.sqrt(max(q, 1e-6))

    wei_len_hint = math.hypot(pier_hint[0] - m_w[0], pier_hint[1] - m_w[1]) or 1.0
    wei_u = ((pier_hint[0] - m_w[0]) / wei_len_hint, (pier_hint[1] - m_w[1]) / wei_len_hint)
    wei_t = 0.72
    wei_cx = m_w[0] + (pier_hint[0] - m_w[0]) * wei_t
    wei_cy = m_w[1] + (pier_hint[1] - m_w[1]) * wei_t
    pier_ang = math.atan2(pier_hint[0] - m_w[0], pier_hint[1] - m_w[1])
    wei_half = _ellipse_half_along(*wei_u, wei_rx, wei_ry)
    wei_near = [wei_cx - wei_u[0] * wei_half, wei_cy - wei_u[1] * wei_half]
    wei_far = [wei_cx + wei_u[0] * wei_half, wei_cy + wei_u[1] * wei_half]
    pier = [wei_cx + wei_u[0] * (wei_half + 22), wei_cy + wei_u[1] * (wei_half + 22)]
    # Bridge length = exact abutment gap so deck meets both road ends
    wei_bridge_len = math.hypot(wei_far[0] - wei_near[0], wei_far[1] - wei_near[1])

    moat_u = ((foothill[0] - Gate[0]) / moat_len, (foothill[1] - Gate[1]) / moat_len)
    moat_half = _ellipse_half_along(*moat_u, moat_rx, moat_ry)
    moat_near = [moat_cx - moat_u[0] * moat_half, moat_cy - moat_u[1] * moat_half]
    moat_far = [moat_cx + moat_u[0] * moat_half, moat_cy + moat_u[1] * moat_half]
    moat_bridge_len = math.hypot(moat_far[0] - moat_near[0], moat_far[1] - moat_near[1])

    water = [
        {
            "x": round(wei_cx, 1), "y": round(wei_cy, 1),
            "rx": wei_rx, "ry": wei_ry, "depth": 3, "diveable": False, "name": "渭水支流",
        },
        {
            "x": round(moat_cx, 1), "y": round(moat_cy, 1),
            "rx": moat_rx, "ry": moat_ry, "depth": 2, "name": "护城河",
        },
    ]
    # Long 渭水: span nearly the full map west edge (N→S), through the stone bridge
    rdx, rdy = math.sin(pier_ang), math.cos(pier_ang)
    px_, py_ = -rdy, rdx
    # Anchor a north–south channel on the west side; bend through wei_cx/cy
    river_x = min(wei_cx, m_w[0] - 40)
    rivers = [{
        "name": "渭水",
        "points": [
            [round(river_x - 30, 1), 40.0],
            [round(river_x - 10, 1), 160.0],
            [round(river_x + 20, 1), 280.0],
            [round(wei_cx + px_ * 80, 1), round(max(360.0, wei_cy + py_ * 80), 1)],
            [round(wei_cx + px_ * 25, 1), round(wei_cy + py_ * 25, 1)],
            [round(wei_cx, 1), round(wei_cy, 1)],
            [round(wei_cx - px_ * 30, 1), round(wei_cy - py_ * 30, 1)],
            [round(wei_cx - px_ * 90 + 20, 1), round(min(H - 80, wei_cy - py_ * 90 + 120), 1)],
            [round(river_x + 10, 1), round(H * 0.72, 1)],
            [round(river_x - 20, 1), round(H * 0.88, 1)],
            [round(river_x - 40, 1), round(H - 30, 1)],
        ],
        "width": 40,
    }]
    bridges = [
        {
            "x": round(wei_cx, 1), "y": round(wei_cy, 1),
            "angle": pier_ang, "length": wei_bridge_len, "name": "渭水石桥",
        },
        {
            "x": round(moat_cx, 1), "y": round(moat_cy, 1),
            "angle": gate_ang, "length": moat_bridge_len, "name": "南门石拱桥",
        },
    ]

    roads = [
        road(m_w, A, "cobble"),
        road(A, m_e, "cobble"),
        road(m_s, A, "cobble"),
        road(A, m_n, "cobble"),
        road(m_e, alley, "cobble"),
        road(alley, junction, "cobble"),
        road(junction, B, "cobble"),
        road(m_s, Gate, "dirt"),
        # Split at moat — gap is water + bridge deck only
        road(Gate, moat_near, "dirt"),
        # ONE continuous climb/descent: far bank → temple (no foothill break)
        road(moat_far, C, "dirt"),
        # Split at 渭水 — gap is river + bridge deck only
        road(m_w, wei_near, "dirt"),
        road(wei_far, pier, "dirt"),
    ]

    def _rk(a, b):
        return ((round(a[0], 1), round(a[1], 1)), (round(b[0], 1), round(b[1], 1)))

    spine = {
        _rk(m_w, A), _rk(A, m_e), _rk(m_s, A), _rk(A, m_n),
        _rk(m_e, alley), _rk(alley, junction), _rk(junction, B),
        _rk(m_s, Gate), _rk(Gate, moat_near), _rk(moat_far, C),
        _rk(m_w, wei_near), _rk(wei_far, pier),
    }

    buildings: list[dict] = []
    occupied: list[tuple[float, float, float, float]] = []

    # ========== URBAN: landmarks first (prime curb), then stalls, then shops ==========
    # Landmarks: front face ~10u from road center → door/path opens onto street
    if not _place_landmark_facing_road(
        buildings, occupied, roads, water, rivers,
        m_w, m_e, t=0.28, side=-1, setback=10, w=34, h=24, pad=3.5,
        name="长安·西市酒肆",
        floors=2, type="commercial", enterable=True, landmark="primary",
        sign="醉仙楼", banner=True, city="长安·西市酒肆",
        modelKey="landmark_tavern", zone="urban",
    ):
        print("warn landmark miss tavern", flush=True)

    stall_plan = [
        (0.14, 1, "果摊"),
        (0.42, -1, "布摊"),  # skip tavern frontage around t=0.28
        (0.52, 1, "书摊"),
        (0.62, -1, "胡饼"),
        (0.72, 1, "酒摊"),
        (0.82, -1, "香料"),
        (0.18, 1, "果摊"),
        (0.55, -1, "布摊"),
    ]
    for i, (tt, side, sign) in enumerate(stall_plan):
        seg = (m_w, m_e) if i < 6 else (m_s, m_n)
        ok = _place_stall_on_street(
            buildings, occupied, roads, water, rivers,
            seg[0], seg[1], t=tt, side=side, sign=sign, city="长安·西市酒肆",
        )
        if not ok:
            ok = _place_stall_on_street(
                buildings, occupied, roads, water, rivers,
                seg[0], seg[1], t=min(0.85, tt + 0.1), side=-side, sign=sign, city="长安·西市酒肆",
            )
        if not ok:
            print(f"warn stall miss {sign} t={tt} side={side}", flush=True)
    _try_add(
        buildings, occupied, roads, water, rivers,
        name="长安·西市酒肆·锦绣坊", x=A[0] - 20, y=A[1] - 82, w=32, h=22,
        floors=1, type="shop", sign="锦绣坊", banner=True, city="长安·西市酒肆",
        curb_min=16, curb_max=70, search=True, zone="urban", pad=4.0,
    )
    _try_add(
        buildings, occupied, roads, water, rivers,
        name="长安·西市酒肆·铁匠铺", x=A[0] + 12, y=A[1] + 28, w=26, h=20,
        floors=1, type="commercial", sign="铁匠铺", city="长安·西市酒肆",
        curb_min=16, curb_max=55, search=True, zone="urban", pad=4.0,
    )
    _try_add(
        buildings, occupied, roads, water, rivers,
        name="长安·西市酒肆·米行", x=A[0] + 44, y=A[1] - 36, w=24, h=20,
        floors=1, type="shop", sign="米行", city="长安·西市酒肆",
        curb_min=16, curb_max=55, search=True, zone="urban", pad=4.0,
    )

    for seg_a, seg_b, spacing in (
        (m_w, m_e, 0.10),
        (m_s, m_n, 0.11),
        (A, alley, 0.12),
        (alley, junction, 0.12),
    ):
        _place_along_road(
            buildings, occupied, roads, water, rivers, rng,
            seg_a, seg_b, sides=(-1, 1), setback=28, spacing=spacing,
            city="长安·西市酒肆", urban=True, zone="urban",
        )

    # Wooden finger pier at shore — rot aims local +X into the river (west)
    _try_add(
        buildings, occupied, roads, water, rivers,
        name="渭水纤道·码头", x=pier[0] - 10, y=pier[1] - 6, w=28, h=14,
        floors=1, type="dock", sign="码头", city="长安·西市酒肆",
        allow_in_water=True, allow_on_road=False, curb_min=0, curb_max=90,
        search=True, zone="urban", rot=math.pi,  # +X → west into 渭水
    )

    # ========== PALACE zone — 四合院 facing 御道 ==========
    if not _place_landmark_facing_road(
        buildings, occupied, roads, water, rivers,
        junction, B, t=0.55, side=-1, setback=10, w=48, h=44, pad=4.0,
        name="大明宫·紫宸殿外",
        floors=2, type="palace", enterable=True, landmark="primary",
        sign="紫宸殿外", city="大明宫·紫宸殿外",
        modelKey="landmark_palace", zone="urban",
    ):
        print("warn landmark miss palace", flush=True)
    _try_add(
        buildings, occupied, roads, water, rivers,
        name="大明宫·御史台偏廊", x=B[0] + 42, y=B[1] - 30, w=36, h=26,
        floors=1, type="office", sign="御史台", city="大明宫·紫宸殿外",
        curb_min=12, curb_max=70, search=True, zone="urban",
    )
    _try_add(
        buildings, occupied, roads, water, rivers,
        name="大明宫·金吾卫署", x=B[0] - 60, y=B[1] - 20, w=32, h=26,
        floors=1, type="office", sign="金吾卫", city="大明宫·紫宸殿外",
        curb_min=12, curb_max=70, search=True, zone="urban",
    )
    # 阙楼 / 城门 — flank the road (never sit on carriageway / bridge approach)
    # Door (+Z) faces the street; clear gap kept for the road through the gate line.
    def _place_gate_flanking(name, road_a, road_b, t, sign, city, side_setback=36):
        ax, ay = road_a
        bx, by = road_b
        length = math.hypot(bx - ax, by - ay) or 1.0
        dx, dy = (bx - ax) / length, (by - ay) / length
        nx, ny = -dy, dx
        cx = ax + (bx - ax) * t
        cy = ay + (by - ay) * t
        # Twin towers left/right of road — road & bridge stay clear of doors
        for side, sfx in ((-1, "西"), (1, "东")):
            fcx = cx + nx * side_setback * side
            fcy = cy + ny * side_setback * side
            gw, gh = 26, 24
            px, py = fcx - gw * 0.5, fcy - gh * 0.5
            yaw = _yaw_face_point(fcx, fcy, cx, cy)
            if any(_aabb_overlap(px, py, gw, gh, ox, oy, ow, oh, pad=3.0) for ox, oy, ow, oh in occupied):
                continue
            # Keep clear of water / bridge span
            if _in_water(fcx, fcy, water, rivers, margin=18):
                continue
            buildings.append(building(
                name=f"{name}·{sfx}", x=round(px, 1), y=round(py, 1), w=gw, h=gh,
                floors=2, type="tower", sign=sign, city=city, zone="urban",
                rot=round(yaw, 3),
            ))
            occupied.append((px, py, gw, gh))

    _place_gate_flanking("大明宫·南阙", junction, B, 0.08, "南阙", "大明宫·紫宸殿外", side_setback=34)
    _place_gate_flanking("长安·南门瓮城", m_s, Gate, 0.92, "南门", "大明宫·紫宸殿外", side_setback=38)

    # ========== RURAL: Gate → foothill — paddies dominate, sparse farmsteads ==========
    fields = []
    for i in range(22):
        t = 0.06 + i * 0.042
        if t > 0.96:
            break
        bx = Gate[0] + (foothill[0] - Gate[0]) * t
        by = Gate[1] + (foothill[1] - Gate[1]) * t
        for ox in (42, 78, -55, -95):
            fx = bx + ox + rng.uniform(-10, 10)
            fy = by + rng.uniform(-14, 14)
            if _in_water(fx, fy, water, rivers, margin=14):
                continue
            if _road_dist(fx, fy, roads) < 24:
                continue
            fields.append({"x": round(fx, 1), "y": round(fy, 1), "w": 52, "h": 34, "kind": "paddy"})

    _place_along_road(
        buildings, occupied, roads, water, rivers, rng,
        Gate, foothill, sides=(-1, 1), setback=48, spacing=0.22,
        city="终南山·城南田野", urban=False, zone="rural",
    )

    # ========== TEMPLE compound (mountain) — courtyard gate on approach road ==========
    if not _place_landmark_facing_road(
        buildings, occupied, roads, water, rivers,
        foothill, C, t=0.72, side=1, setback=10, w=42, h=36, pad=3.5,
        name="终南山·古观",
        floors=1, type="temple", enterable=True, landmark="primary",
        sign="终南古观", city="终南山·古观",
        modelKey="landmark_temple", zone="sacred",
    ):
        print("warn landmark miss temple", flush=True)
    _try_add(
        buildings, occupied, roads, water, rivers,
        name="终南山·古观·残碑院", x=C[0] + 32, y=C[1] - 28, w=28, h=24,
        floors=1, type="temple", city="终南山·古观",
        curb_min=14, curb_max=90, search=True, zone="sacred",
    )
    _try_add(
        buildings, occupied, roads, water, rivers,
        name="终南山·古观·侧廊", x=C[0] - 48, y=C[1] + 8, w=26, h=20,
        floors=1, type="residential", city="终南山·古观",
        curb_min=14, curb_max=90, search=True, zone="sacred",
    )
    _try_add(
        buildings, occupied, roads, water, rivers,
        name="终南道边·茶棚", x=(foothill[0] + C[0]) / 2 + 36, y=(foothill[1] + C[1]) / 2 - 10,
        w=18, h=14, floors=1, type="shop", sign="茶棚", city="终南山·古观",
        curb_min=16, curb_max=60, search=True, zone="sacred",
    )

    # Trees: sparse in urban, orchard-like in rural, dense on mountain
    trees = []
    for _ in range(18):  # urban street trees few
        tx = A[0] + rng.uniform(-90, 110)
        ty = A[1] + rng.uniform(-70, 80)
        if _in_water(tx, ty, water, rivers) or _road_dist(tx, ty, roads) < 8:
            continue
        trees.append({"x": round(tx, 1), "y": round(ty, 1), "climbable": False})
    for _ in range(40):  # rural cypress / willow along paddies
        tx = Gate[0] + rng.uniform(-100, 120)
        ty = Gate[1] + rng.uniform(20, 280)
        if _in_water(tx, ty, water, rivers) or _road_dist(tx, ty, roads) < 10:
            continue
        trees.append({"x": round(tx, 1), "y": round(ty, 1), "climbable": False})
    for _ in range(90):  # mountain forest
        tx = C[0] + rng.uniform(-140, 140)
        ty = C[1] + rng.uniform(-60, 180)
        if _road_dist(tx, ty, roads) < 10:
            continue
        trees.append({"x": round(tx, 1), "y": round(ty, 1), "climbable": False})

    # Street props — ONLY purposeful curb fixtures (no random box clutter)
    props: list[dict] = []

    def _add_prop(kind: str, px: float, py: float, rot: float = 0.0, scale: float = 1.0) -> None:
        if _in_water(px, py, water, rivers, margin=6):
            return
        if _road_dist(px, py, roads) < 8.0:
            return
        # Skip props that land inside a building footprint (+ margin)
        for ox, oy, ow, oh in occupied:
            if ox - 2 <= px <= ox + ow + 2 and oy - 2 <= py <= oy + oh + 2:
                return
        props.append({
            "kind": kind,
            "x": round(px, 1),
            "y": round(py, 1),
            "rot": round(rot, 3),
            "scale": round(scale, 2),
        })

    # Lanterns every ~street block on market streets (curb, facing out)
    for seg_a, seg_b in ((m_w, m_e), (m_s, m_n), (alley, junction)):
        ax, ay = seg_a
        bx, by = seg_b
        length = math.hypot(bx - ax, by - ay) or 1.0
        dx, dy = (bx - ax) / length, (by - ay) / length
        nx, ny = -dy, dx
        for t in (0.15, 0.35, 0.55, 0.75):
            cx = ax + (bx - ax) * t
            cy = ay + (by - ay) * t
            for side in (-1, 1):
                _add_prop("lantern", cx + nx * 13 * side, cy + ny * 13 * side, scale=1.05)

    # Tavern door: wine jars + banner poles (forecourt facing street)
    for i, kind in enumerate(["banner", "wine_jar", "wine_jar", "lantern"]):
        _add_prop(kind, A[0] - 8 + i * 8, A[1] + 30, rot=0.0, scale=1.05)

    # Palace approach: paired stone lions + lanterns
    for sx in (-1, 1):
        _add_prop("stone_lion", B[0] + sx * 28, B[1] + 42, rot=0 if sx > 0 else math.pi, scale=1.2)
        _add_prop("lantern", B[0] + sx * 38, B[1] + 58, scale=1.1)

    # Rural: wells near farmsteads only
    for b in buildings:
        if b.get("zone") != "rural":
            continue
        _add_prop("well", b["x"] + b["w"] + 10, b["y"] + b["h"] * 0.5, scale=1.0)

    # Temple: stone lions flanking approach
    for sx in (-1, 1):
        _add_prop("stone_lion", C[0] + sx * 22, C[1] + 36, rot=0 if sx > 0 else math.pi, scale=1.1)
        _add_prop("lantern", C[0] + sx * 30, C[1] + 48, scale=1.0)

    # Face buildings to streets, then drop any road with no frontage
    _orient_buildings_to_roads(buildings, roads)
    roads = _prune_orphan_roads(roads, buildings, keep_spine=spine)

    factions = [
        {"name": "长安·西市酒肆", "x": cities[0]["x"], "y": cities[0]["y"], "r": 110, "color": [210, 110, 110], "terrain": "valley"},
        {"name": "大明宫·紫宸殿外", "x": cities[1]["x"], "y": cities[1]["y"], "r": 120, "color": [110, 170, 210], "terrain": "hill"},
        {"name": "终南山·古观", "x": cities[2]["x"], "y": cities[2]["y"], "r": 75, "color": [200, 180, 100], "terrain": "peak"},
        # Hill (not sharp peak) so the mountain road can grade instead of floating
        {"name": "终南前缓坡", "x": round(foothill[0], 1), "y": round(foothill[1], 1), "r": 130, "color": [120, 110, 95], "terrain": "hill"},
        {"name": "宫城台地", "x": round(B[0], 1), "y": round(B[1] - 40, 1), "r": 105, "color": [130, 120, 100], "terrain": "hill"},
        {"name": "城南稻田", "x": round((Gate[0] + foothill[0]) / 2, 1), "y": round((Gate[1] + foothill[1]) / 2, 1), "r": 160, "color": [90, 120, 70], "terrain": "valley"},
    ]

    locations = [
        {"name": c["name"], "x": c["x"], "y": c["y"], "building": True, "enterable": True}
        for c in cities
    ]
    landmarks = [
        {"id": "lm_west_market", "name": "长安·西市酒肆", "tier": "primary", "x": A[0], "y": A[1], "building_type": "commercial", "city": "长安·西市酒肆"},
        {"id": "lm_palace", "name": "大明宫·紫宸殿外", "tier": "primary", "x": B[0], "y": B[1], "building_type": "palace", "city": "大明宫·紫宸殿外"},
        {"id": "lm_temple", "name": "终南山·古观", "tier": "primary", "x": C[0], "y": C[1], "building_type": "temple", "city": "终南山·古观"},
    ]
    camera_anchors = [
        # Spawn on market E–W centerline (A), looking along the stalls
        {"id": "spawn", "role": "spawn", "x": round(A[0], 1), "y": round(A[1], 1), "yaw": 0.0, "pitch": -0.32, "distance": 16},
        {"id": "palace_view", "x": round(B[0], 1), "y": round(B[1] + 60, 1), "distance": 36},
        {"id": "rural_view", "x": round((Gate[0] + foothill[0]) / 2, 1), "y": round((Gate[1] + foothill[1]) / 2, 1), "distance": 40},
    ]

    # Audit counts
    urban_n = sum(1 for b in buildings if b.get("zone") == "urban")
    rural_n = sum(1 for b in buildings if b.get("zone") == "rural")
    sacred_n = sum(1 for b in buildings if b.get("zone") == "sacred")

    layout = {
        "width": W,
        "height": H,
        "name": brief["name"],
        "genre": "ancient",
        "mapVersion": 2,
        "locations": locations,
        "factions": factions,
        "cities": cities,
        "buildings": buildings,
        "roads": roads,
        "water": water,
        "rivers": rivers,
        "fields": fields,
        "trees": trees,
        "props": props,
        "bridges": bridges,
        "landmarks": landmarks,
        "camera_anchors": camera_anchors,
        "zones": {
            "urban": ["长安·西市酒肆", "大明宫·紫宸殿外"],
            "rural": ["终南山·城南田野"],
            "sacred": ["终南山·古观"],
        },
        "terrain": {
            "seed": 91021,
            "maxHeight": 34,
            "waterLevel": -0.34,
            "worldScale": round(world_scale, 3),
            "vegetation": "城内稀疏行道柏；城南连片稻田；终南密林",
            "shape": "river_plains_v2",
            "metersPerMap": {"x": round(span_x / W, 4), "y": round(span_y / H, 4)},
            "bounds_m": {"xmin": xmin, "xmax": xmax, "ymin": ymin, "ymax": ymax},
        },
        "mapBrief": {
            "version": 2,
            "revision": "roads8",
            "premise": brief["premise"],
            "source": "map_briefs_v2",
            "paint": "procedural_v2",
            "cast": [c["name"] for c in brief["cast"]],
            "placement_rules": [
                "非码头建筑禁止落入水面",
                "非城门/阙楼/牌坊禁止压道路中心线",
                "城镇路边带密铺，乡村大退距+稻田主导",
                "西市正交十字街，干道从十字端点出发不重叠",
            ],
        },
        "distanceAudit": {
            "revision": "roads8",
            "A_B_path_m_target": dist["pair_distances_m"]["A↔B_步行官道"]["path_m"],
            "A_C_path_m_target": dist["pair_distances_m"]["A↔C_出城登山"]["path_m"],
            "worldScale": round(world_scale, 3),
            "urban_buildings": urban_n,
            "rural_buildings": rural_n,
            "sacred_buildings": sacred_n,
            "fields": len(fields),
            "props": len(props),
            "landmarks": ["landmark_tavern", "landmark_palace", "landmark_temple"],
        },
    }
    return layout


def paint_overview(layout: dict, brief: dict, out: Path) -> None:
    img = Image.new("RGB", (W, H), (72, 62, 48))
    draw = ImageDraw.Draw(img)
    # terrain wash
    for y in range(0, H, 4):
        for x in range(0, W, 4):
            t = y / H
            col = (
                int(90 + 40 * (1 - t)),
                int(76 + 30 * (1 - t)),
                int(52 + 20 * t),
            )
            draw.rectangle([x, y, x + 4, y + 4], fill=col)

    for w in layout.get("water") or []:
        draw.ellipse(
            [w["x"] - w["rx"], w["y"] - w["ry"], w["x"] + w["rx"], w["y"] + w["ry"]],
            fill=(52, 76, 96),
        )
    for river in layout.get("rivers") or []:
        pts = [(p[0], p[1]) for p in river["points"]]
        if len(pts) >= 2:
            draw.line(pts, fill=(48, 70, 92), width=max(6, river.get("width", 20) // 3))

    for road in layout.get("roads") or []:
        draw.line([tuple(road["from"]), tuple(road["to"])], fill=(160, 140, 100), width=10)
        draw.line([tuple(road["from"]), tuple(road["to"])], fill=(200, 178, 130), width=4)

    for f in layout.get("fields") or []:
        draw.rectangle(
            [f["x"], f["y"], f["x"] + f["w"] * 0.7, f["y"] + f["h"] * 0.7],
            fill=(58, 98, 52), outline=(48, 78, 42),
        )

    for t in layout.get("trees") or []:
        draw.ellipse([t["x"] - 2, t["y"] - 2, t["x"] + 2, t["y"] + 2], fill=(40, 70, 35))

    for b in layout.get("buildings") or []:
        zone = b.get("zone")
        col = {
            "palace": (180, 60, 50),
            "temple": (160, 140, 120),
            "commercial": (140, 110, 70),
            "shop": (150, 120, 80),
            "office": (120, 100, 90),
            "tower": (100, 80, 70),
            "residential": (130, 115, 95),
            "stall": (170, 130, 60),
            "dock": (90, 110, 130),
        }.get(b.get("type"), (120, 100, 80))
        if zone == "rural":
            col = (110, 100, 70)
        elif zone == "urban" and b.get("type") in ("commercial", "shop", "residential"):
            col = (155, 105, 55)
        # Full footprint — overview must match collision reality
        draw.rectangle(
            [b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"]],
            fill=col, outline=(30, 22, 14),
        )

    for c in layout.get("cities") or []:
        draw.ellipse([c["x"] - 6, c["y"] - 6, c["x"] + 6, c["y"] + 6], fill=(220, 190, 120), outline=(240, 224, 180))
        draw.text((c["x"] + 8, c["y"] - 8), c["name"][:10], fill=(240, 224, 180))

    draw.rectangle([0, 0, W, 36], fill=(50, 40, 30))
    draw.text((12, 10), f"{brief['name']}  ·  map v2  ·  scale {layout['terrain']['worldScale']}", fill=(240, 224, 180))
    img = img.filter(ImageFilter.GaussianBlur(radius=0.4))
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")


def try_dit(brief: dict, out: Path) -> bool:
    if not VENV_PY.is_file() or not T2I_CLI.is_file():
        return False
    tmp = out.with_suffix(".dit.png")
    prompt = (brief.get("master_prompt") or "")[:200]
    import os
    import subprocess
    cmd = [
        str(VENV_PY), "-u", str(T2I_CLI), prompt,
        "-o", str(tmp), "--device", "cpu", "--seed", "3647",
        "--kind", "map", "--steps", "12", "--size", "768",
    ]
    env = {**os.environ, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "PYTHONUNBUFFERED": "1"}
    print("dit paint ancient …", flush=True)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600, env=env)
    except Exception as exc:
        print("dit fail", exc, flush=True)
        return False
    if proc.returncode != 0 or not tmp.is_file():
        print("dit fail", (proc.stderr or proc.stdout)[:400], flush=True)
        return False
    Image.open(tmp).convert("RGB").resize((W, H)).save(out, "PNG")
    tmp.unlink(missing_ok=True)
    print("dit ok", flush=True)
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--civ", default="ancient")
    ap.add_argument("--dit", action="store_true")
    args = ap.parse_args()
    if args.civ != "ancient":
        raise SystemExit("v2 builder currently implements ancient only; others next")

    brief = load_brief(args.civ)
    layout = build_ancient(brief)
    OUT_MAPS.mkdir(parents=True, exist_ok=True)
    RUNTIME.mkdir(parents=True, exist_ok=True)

    json_path = OUT_MAPS / f"{args.civ}.json"
    png_path = OUT_MAPS / f"{args.civ}.png"
    json_path.write_text(json.dumps(layout, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    painted = False
    if args.dit:
        painted = try_dit(brief, png_path)
    if not painted:
        paint_overview(layout, brief, png_path)
        layout["mapBrief"]["paint"] = "procedural_v2"
    else:
        layout["mapBrief"]["paint"] = "hunyuan_dit"
        json_path.write_text(json.dumps(layout, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    civ_map = CIV_ROOT / args.civ / "map"
    civ_map.mkdir(parents=True, exist_ok=True)
    (civ_map / "layout.json").write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
    (civ_map / "overview.png").write_bytes(png_path.read_bytes())
    (RUNTIME / f"{args.civ}.json").write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
    (RUNTIME / f"{args.civ}.png").write_bytes(png_path.read_bytes())

    # update index entry for ancient
    idx_path = OUT_MAPS / "index.json"
    idx = {"maps": []}
    if idx_path.is_file():
        idx = json.loads(idx_path.read_text(encoding="utf-8"))
    maps = [m for m in idx.get("maps", []) if m.get("civ") != args.civ]
    maps.insert(0, {
        "civ": args.civ,
        "name": brief["name"],
        "png": f"frontend/public/maps/{args.civ}.png",
        "json": f"frontend/public/maps/{args.civ}.json",
        "dit": painted,
        "scale": layout["terrain"]["worldScale"],
        "maxHeight": layout["terrain"]["maxHeight"],
        "vegetation": layout["terrain"]["vegetation"],
        "cities": len(layout["cities"]),
        "mapVersion": 2,
    })
    idx_path.write_text(json.dumps({"maps": maps}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"ok {args.civ} v2 buildings={len(layout['buildings'])} roads={len(layout['roads'])} "
          f"worldScale={layout['terrain']['worldScale']} size={W}x{H} dit={painted}")
    print(f"  A={layout['cities'][0]} B={layout['cities'][1]} C={layout['cities'][2]}")


if __name__ == "__main__":
    main()
