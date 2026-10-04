#!/usr/bin/env python3
"""
Build genre building kits as multi-material GLB files (Eastern / modern / sci-fi).
Uses baseColorFactor materials (no COLOR_0) so Three.js always shades them visibly.
"""
from __future__ import annotations

import json
import math
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "frontend" / "public" / "models" / "buildings"


def pad4(n: int) -> int:
  return (4 - (n % 4)) % 4


def write_glb_parts(path: Path, parts: list[dict]):
  """
  parts: [{positions, normals, indices, rgba}]
  One mesh with multiple primitives, each with its own PBR material.
  """
  import array

  blob = bytearray()

  def align():
    while len(blob) % 4:
      blob.append(0)

  accessors = []
  buffer_views = []
  materials = []
  primitives = []

  for pi, part in enumerate(parts):
    positions = part["positions"]
    normals = part["normals"]
    indices = part["indices"]
    rgba = part["rgba"]
    if not indices:
      continue

    pos = array.array("f", positions)
    nor = array.array("f", normals)
    idx = array.array("H", indices) if max(indices) < 65535 else array.array("I", indices)

    pos_off = len(blob)
    blob.extend(pos.tobytes()); align()
    nor_off = len(blob)
    blob.extend(nor.tobytes()); align()
    idx_off = len(blob)
    blob.extend(idx.tobytes()); align()

    nvert = len(positions) // 3
    xs = positions[0::3]; ys = positions[1::3]; zs = positions[2::3]
    mn = [min(xs), min(ys), min(zs)]
    mx = [max(xs), max(ys), max(zs)]
    idx_comp = 5123 if idx.typecode == "H" else 5125

    ai = len(accessors)
    accessors.extend([
      {"bufferView": len(buffer_views), "componentType": 5126, "count": nvert, "type": "VEC3", "min": mn, "max": mx},
      {"bufferView": len(buffer_views) + 1, "componentType": 5126, "count": nvert, "type": "VEC3"},
      {"bufferView": len(buffer_views) + 2, "componentType": idx_comp, "count": len(indices), "type": "SCALAR"},
    ])
    buffer_views.extend([
      {"buffer": 0, "byteOffset": pos_off, "byteLength": nvert * 12},
      {"buffer": 0, "byteOffset": nor_off, "byteLength": nvert * 12},
      {"buffer": 0, "byteOffset": idx_off, "byteLength": len(idx) * idx.itemsize},
    ])
    mi = len(materials)
    materials.append({
      "name": f"mat_{pi}",
      "pbrMetallicRoughness": {
        "baseColorFactor": list(rgba),
        "metallicFactor": 0.04,
        "roughnessFactor": 0.78,
      },
      "doubleSided": True,
    })
    primitives.append({
      "attributes": {"POSITION": ai, "NORMAL": ai + 1},
      "indices": ai + 2,
      "material": mi,
    })

  if not primitives:
    raise ValueError(f"empty kit {path}")

  js = {
    "asset": {"version": "2.0", "generator": "civsim-arch-kits-v2"},
    "scenes": [{"nodes": [0]}],
    "scene": 0,
    "nodes": [{"mesh": 0}],
    "meshes": [{"primitives": primitives}],
    "materials": materials,
    "accessors": accessors,
    "bufferViews": buffer_views,
    "buffers": [{"byteLength": len(blob)}],
  }

  jb = json.dumps(js, separators=(",", ":")).encode("utf-8")
  jb += b" " * pad4(len(jb))
  blob = bytes(blob) + b"\x00" * pad4(len(blob))
  total = 12 + 8 + len(jb) + 8 + len(blob)
  out = bytearray()
  out += struct.pack("<4sII", b"glTF", 2, total)
  out += struct.pack("<I4s", len(jb), b"JSON")
  out += jb
  out += struct.pack("<I4s", len(blob), b"BIN\x00")
  out += blob
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_bytes(out)


class Mesh:
  """Accumulates colored boxes/roofs as separate material parts."""

  def __init__(self):
    self.parts: dict[tuple, dict] = {}

  def _part(self, rgb):
    key = (round(rgb[0], 3), round(rgb[1], 3), round(rgb[2], 3))
    if key not in self.parts:
      self.parts[key] = {
        "positions": [], "normals": [], "indices": [],
        "rgba": [key[0], key[1], key[2], 1.0],
      }
    return self.parts[key]

  def box(self, cx, cy, cz, sx, sy, sz, rgb, *, sink=0.0):
    cy = cy + sink
    hx, hy, hz = sx / 2, sy / 2, sz / 2
    corners = [
      (cx - hx, cy - hy, cz - hz),
      (cx + hx, cy - hy, cz - hz),
      (cx + hx, cy + hy, cz - hz),
      (cx - hx, cy + hy, cz - hz),
      (cx - hx, cy - hy, cz + hz),
      (cx + hx, cy - hy, cz + hz),
      (cx + hx, cy + hy, cz + hz),
      (cx - hx, cy + hy, cz + hz),
    ]
    faces = [
      (0, 1, 2, 3, (0, 0, -1)),
      (5, 4, 7, 6, (0, 0, 1)),
      (4, 0, 3, 7, (-1, 0, 0)),
      (1, 5, 6, 2, (1, 0, 0)),
      (3, 2, 6, 7, (0, 1, 0)),
      (4, 5, 1, 0, (0, -1, 0)),
    ]
    p = self._part(rgb)
    for a, c, d, e, n in faces:
      base = len(p["positions"]) // 3
      for i in (a, c, d, e):
        x, y, z = corners[i]
        p["positions"].extend([x, y, z])
        p["normals"].extend(list(n))
      p["indices"].extend([base, base + 1, base + 2, base, base + 2, base + 3])

  def hip_roof(self, cx, cy, cz, w, d, h, rgb, ridge_rgb=None):
    hw, hd = w / 2, d / 2
    rw = w * 0.08
    A = (cx - hw, cy, cz + hd)
    B = (cx + hw, cy, cz + hd)
    C = (cx + hw, cy, cz - hd)
    D = (cx - hw, cy, cz - hd)
    R0 = (cx - rw, cy + h, cz)
    R1 = (cx + rw, cy + h, cz)
    tris = [
      (A, B, R1), (A, R1, R0),
      (B, C, R1),
      (C, D, R0), (C, R0, R1),
      (D, A, R0),
    ]
    p = self._part(rgb)
    for p0, p1, p2 in tris:
      ux, uy, uz = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
      vx, vy, vz = p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]
      nx = uy * vz - uz * vy
      ny = uz * vx - ux * vz
      nz = ux * vy - uy * vx
      ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1
      n = (nx / ln, ny / ln, nz / ln)
      base = len(p["positions"]) // 3
      for pt in (p0, p1, p2):
        p["positions"].extend(pt)
        p["normals"].extend(n)
      p["indices"].extend([base, base + 1, base + 2])
    if ridge_rgb:
      self.box(cx, cy + h + 0.04, cz, w * 0.22, 0.08, 0.1, ridge_rgb)

  def save(self, path: Path):
    write_glb_parts(path, list(self.parts.values()))


def eastern_house(path: Path, *, kind="residential", genre="ancient"):
  m = Mesh()
  if genre == "xuanhuan":
    wall, wood, roof = (0.92, 0.90, 0.98), (0.35, 0.15, 0.55), (0.42, 0.18, 0.72)
  else:
    wall, wood, roof = (0.93, 0.90, 0.84), (0.32, 0.22, 0.16), (0.55, 0.10, 0.12)

  bw, bd, bh = 3.8, 3.3, 2.6
  if kind == "palace":
    bw, bd, bh = 6.2, 5.0, 3.4
  elif kind == "temple":
    bw, bd, bh = 5.0, 4.4, 3.0
  elif kind == "commercial":
    bw, bd, bh = 4.4, 3.5, 2.7
  elif kind == "shop":
    bw, bd, bh = 3.4, 2.9, 2.4
  elif kind == "tower":
    bw, bd, bh = 3.6, 3.6, 5.2

  m.box(0, 0.06, bd * 0.52, bw * 0.28, 0.12, 0.4, (0.55, 0.52, 0.48))
  for sx in (-1, 1):
    for sz in (-1, 1):
      m.box(sx * bw * 0.42, bh / 2, sz * bd * 0.42, 0.28, bh, 0.28, wood)
  m.box(0, bh / 2, 0, bw * 0.82, bh, bd * 0.82, wall)
  m.box(0, bh + 0.08, 0, bw * 0.95, 0.18, bd * 0.95, wood)
  m.box(0, 0.85, bd * 0.42, 0.9, 1.7, 0.12, (0.18, 0.14, 0.12))
  lit = (0.95, 0.85, 0.45) if genre != "xuanhuan" else (0.75, 0.65, 0.95)
  m.box(-bw * 0.22, 1.45, bd * 0.42, 0.7, 0.85, 0.08, lit)
  m.box(bw * 0.22, 1.45, bd * 0.42, 0.7, 0.85, 0.08, lit)

  layers = 3 if kind in ("palace", "temple") else (2 if kind == "commercial" else 1)
  for i in range(layers):
    scale = 1.18 + (layers - i) * 0.12
    y = bh + 0.2 + i * 0.95
    m.hip_roof(0, y, 0, bw * scale, bd * scale, 0.85 + (0.25 if kind in ("palace", "temple") else 0), roof, wood)
    if kind in ("palace", "temple"):
      m.box(0, y + 1.05, 0, 0.25, 0.25, 0.25, (0.72, 0.45, 0.12))

  if kind in ("commercial", "shop"):
    m.box(0, bh * 0.55, bd * 0.44, min(bw * 0.7, 3.2), 0.45, 0.1, (0.45, 0.15, 0.08))

  m.save(path)


def modern_building(path: Path, *, kind="residential", noir=False, scifi=False, theme: str | None = None):
  m = Mesh()
  # military prefers squat volumes
  if theme == "military":
    floors = {"tower": 4, "office": 2, "commercial": 1, "shop": 1, "residential": 2, "palace": 3}.get(kind, 2)
    story = 2.6
    bw = 8.0 if kind in ("commercial", "palace") else 6.5
    bd = 7.0 if kind in ("commercial", "palace") else 5.5
  else:
    floors = {"tower": 10, "office": 7, "commercial": 4, "shop": 2, "residential": 3, "palace": 6}.get(kind, 4)
    story = 2.8
    bw = 7.0 if kind != "tower" else 8.5
    bd = 6.0 if kind != "tower" else 8.5
  if kind == "shop":
    bw, bd, floors = 5.0, 4.2, 2
  if theme == "enterprise" and kind in ("office", "commercial"):
    floors = max(3, floors - 2)
    bw, bd = 7.5, 6.5
  if theme == "securities" and kind == "tower":
    floors = 12
    bw, bd = 9.0, 9.0
  bh = floors * story

  if scifi:
    wall, accent, win = (0.42, 0.52, 0.62), (0.12, 0.72, 0.82), (0.45, 0.92, 0.98)
  elif noir:
    wall, accent, win = (0.42, 0.38, 0.35), (0.45, 0.12, 0.16), (0.65, 0.4, 0.35)
  elif theme == "enterprise":
    wall, accent, win = (0.72, 0.86, 0.84), (0.15, 0.55, 0.58), (0.55, 0.88, 0.90)
  elif theme == "securities":
    wall, accent, win = (0.55, 0.60, 0.68), (0.72, 0.55, 0.18), (0.40, 0.62, 0.85)
  elif theme == "military":
    wall, accent, win = (0.52, 0.50, 0.40), (0.38, 0.42, 0.30), (0.55, 0.58, 0.42)
  else:
    wall, accent, win = (0.78, 0.82, 0.86), (0.28, 0.32, 0.38), (0.45, 0.75, 0.90)

  m.box(0, bh / 2, 0, bw, bh, bd, wall)

  for fi in range(floors):
    wy = 1.2 + fi * story
    for fx, fz, span_axis in [
      (0, bd / 2 + 0.04, "x"),
      (0, -bd / 2 - 0.04, "x"),
      (bw / 2 + 0.04, 0, "z"),
      (-bw / 2 - 0.04, 0, "z"),
    ]:
      span = bw if span_axis == "x" else bd
      cols = 4 if kind == "tower" else (2 if theme == "military" else 3)
      for ci in range(cols):
        wx = -span * 0.32 + ci * (span * 0.64 / max(cols - 1, 1))
        if span_axis == "x":
          m.box(wx, wy, fz, span * 0.16, story * 0.55, 0.08, win)
        else:
          m.box(fx, wy, wx, 0.08, story * 0.55, span * 0.16, win)

  for sx in (-1, 1):
    for sz in (-1, 1):
      m.box(sx * bw * 0.52, bh / 2, sz * bd * 0.52, 0.25, bh * 1.02, 0.25, accent)

  roof = (
    (0.75, 0.88, 0.92) if scifi
    else (0.55, 0.5, 0.48) if noir
    else (0.45, 0.48, 0.38) if theme == "military"
    else (0.85, 0.92, 0.90) if theme == "enterprise"
    else (0.35, 0.40, 0.48) if theme == "securities"
    else (0.92, 0.94, 0.96)
  )
  m.box(0, bh + 0.18, 0, bw * 1.02, 0.35, bd * 1.02, roof)
  if kind in ("tower", "office", "palace") and theme != "military":
    m.box(bw * 0.15, bh + 1.0, 0, 0.8, 1.6, 0.8, accent)
  if theme == "military" and kind in ("commercial", "palace"):
    # bunker berm / sandbag strip
    m.box(0, 0.35, bd / 2 + 0.35, bw * 0.9, 0.7, 0.55, (0.48, 0.46, 0.36))
  if scifi:
    m.box(-bw / 2 - 0.08, bh / 2, 0, 0.15, bh * 0.9, bd * 0.55, win)
  if theme == "enterprise":
    # atrium glass ribbon
    m.box(0, bh * 0.45, bd / 2 + 0.06, bw * 0.55, bh * 0.55, 0.1, win)
  if theme == "securities" and kind in ("tower", "palace"):
    m.box(0, bh * 0.55, bd / 2 + 0.06, bw * 0.7, bh * 0.35, 0.1, (0.85, 0.72, 0.28))

  m.save(path)


def dock_glb(path: Path, scifi=False):
  m = Mesh()
  wood = (0.12, 0.55, 0.65) if scifi else (0.45, 0.32, 0.18)
  m.box(0, 0.15, 0, 8.0, 0.3, 3.2, wood)
  for i in range(5):
    m.box(-3 + i * 1.5, -0.4, 0, 0.25, 1.0, 0.25, wood)
  m.save(path)


def build_all():
  classic = ["ancient", "wuxia", "xuanhuan"]
  roles = ["residential", "commercial", "shop", "temple", "palace", "tower"]
  for g in classic:
    for role in roles:
      variants = ["_a", "_b"] if role in ("residential", "commercial", "temple") else [""]
      if role == "temple":
        variants = ["_a", "_b", "_c"]
      if role == "tower":
        variants = ["_a"]
      for v in variants:
        name = f"{role}{v}.glb" if v else f"{role}.glb"
        eastern_house(ROOT / g / name, kind=role, genre=g)
    dock_glb(ROOT / g / "dock.glb")
    eastern_house(ROOT / g / "office.glb", kind="palace", genre=g)

  for g, noir, scifi in [("modern", False, False), ("mystery", True, False), ("scifi", False, True)]:
    for role in ["residential", "commercial", "shop", "office", "tower", "palace"]:
      variants = ["_a", "_b", "_c"] if role in ("residential", "commercial", "tower") else ["_a", "_b"] if role == "office" else [""]
      if role == "shop":
        variants = ["_a", "_b"]
      if role == "palace":
        variants = [""]
      for v in variants:
        name = f"{role}{v}.glb" if v else f"{role}.glb"
        modern_building(ROOT / g / name, kind=role, noir=noir, scifi=scifi)
    dock_glb(ROOT / g / "dock.glb", scifi=scifi)
    if g == "scifi":
      modern_building(ROOT / g / "ship_port_a.glb", kind="tower", scifi=True)
      modern_building(ROOT / g / "ship_port_b.glb", kind="palace", scifi=True)
    modern_building(ROOT / g / "warehouse.glb", kind="commercial", noir=noir, scifi=scifi)

  # Story-matched civ kits: campus glass / finance steel / military bunker
  for g in ("enterprise", "securities", "military"):
    for role in ["residential", "commercial", "shop", "office", "tower", "palace"]:
      variants = ["_a", "_b", "_c"] if role in ("residential", "commercial", "tower") else ["_a", "_b"] if role == "office" else [""]
      if role == "shop":
        variants = ["_a", "_b"]
      if role == "palace":
        variants = [""]
      for v in variants:
        name = f"{role}{v}.glb" if v else f"{role}.glb"
        modern_building(ROOT / g / name, kind=role, theme=g)
    dock_glb(ROOT / g / "dock.glb", scifi=False)
    modern_building(ROOT / g / "warehouse.glb", kind="commercial", theme=g)

  print("kits written under", ROOT)


if __name__ == "__main__":
  build_all()
