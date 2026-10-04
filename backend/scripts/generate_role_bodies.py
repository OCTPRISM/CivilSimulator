#!/usr/bin/env python3
"""Generate ONE unique stylized GLB humanoid per role + 4 skin PBR packs.

Not Mixamo remaps / not runtime geometric hats — each role is its own .glb with
baked clothing silhouette matching genre art direction:

  wuxia     → 射雕/仙剑：劲装、广袖、束发髻、披风轮廓
  ancient   → 汉唐明：交领深衣、襆头/发髻、袍袖
  scifi     → 机械/特战/宇航：硬表面甲、头盔、背包
  xuanhuan  → 西游：僧袍/天将甲/紧身兽纹、佛冠/束发
  mystery   → 福尔摩斯：猎鹿帽、披风大衣、马甲

Stdlib only (struct/json/zlib/math). Re-run:
  python3 backend/scripts/generate_role_bodies.py
"""
from __future__ import annotations

import json
import math
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "frontend" / "public" / "models" / "characters" / "roles"
SKIN_NAMES = ("fair", "tan", "warm", "pale")  # 4 selectable skins per body


# ---------------------------------------------------------------------------
# PNG writer
# ---------------------------------------------------------------------------
def write_png(path: Path, w: int, h: int, rgba_fn) -> None:
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        for x in range(w):
            r, g, b, a = rgba_fn(x, y)
            raw.extend((r & 255, g & 255, b & 255, a & 255))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
        + chunk(b"IEND", b"")
    )


def noise(x: float, y: float) -> float:
    n = math.sin(x * 12.9898 + y * 78.233) * 43758.5453
    return n - math.floor(n)


def fbm(x: float, y: float, octaves: int = 3) -> float:
    a, f, t, n = 0.5, 1.0, 0.0, 0.0
    for _ in range(octaves):
        t += a * noise(x * f, y * f)
        n += a
        a *= 0.5
        f *= 2.05
    return t / max(1e-6, n)


SKIN_BASE = {
    "fair": (232, 201, 168),
    "tan": (196, 148, 100),
    "warm": (201, 146, 94),
    "pale": (240, 220, 200),
}


def gen_skin_pack(role_dir: Path, skin_id: str) -> None:
    br, bg, bb = SKIN_BASE[skin_id]
    d = role_dir / "skins" / skin_id

    def albedo(x, y):
        n = fbm(x * 0.07, y * 0.07)
        pore = 1.0 - 0.07 * noise(x * 0.9, y * 0.9)
        v = (0.88 + 0.16 * n) * pore
        return int(min(255, br * v)), int(min(255, bg * v)), int(min(255, bb * v * 0.98)), 255

    def rough(x, y):
        v = int(100 + 70 * fbm(x * 0.12, y * 0.12))
        return v, v, v, 255

    def normal(x, y):
        h0 = fbm(x * 0.2, y * 0.2)
        hx = fbm((x + 1) * 0.2, y * 0.2)
        hy = fbm(x * 0.2, (y + 1) * 0.2)
        return int((0.5 + (hx - h0) * 2) * 255), int((0.5 + (hy - h0) * 2) * 255), 255, 255

    def metal(_x, _y):
        return 6, 6, 6, 255

    write_png(d / "albedo.png", 256, 256, albedo)
    write_png(d / "roughness.png", 256, 256, rough)
    write_png(d / "normal.png", 256, 256, normal)
    write_png(d / "metalness.png", 128, 128, metal)


# ---------------------------------------------------------------------------
# Minimal GLB writer (static meshes, named materials Skin/Cloth/Metal/Hair)
# ---------------------------------------------------------------------------
class MeshBuf:
    def __init__(self):
        self.positions: list[float] = []
        self.normals: list[float] = []
        self.uvs: list[float] = []
        self.indices: list[int] = []

    def add_box(self, cx, cy, cz, sx, sy, sz, u0=0.0, v0=0.0):
        hx, hy, hz = sx * 0.5, sy * 0.5, sz * 0.5
        # 6 faces, each 4 verts
        faces = [
            # +Z
            ((-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz), (0, 0, 1)),
            # -Z
            ((hx, -hy, -hz), (-hx, -hy, -hz), (-hx, hy, -hz), (hx, hy, -hz), (0, 0, -1)),
            # +Y
            ((-hx, hy, hz), (hx, hy, hz), (hx, hy, -hz), (-hx, hy, -hz), (0, 1, 0)),
            # -Y
            ((-hx, -hy, -hz), (hx, -hy, -hz), (hx, -hy, hz), (-hx, -hy, hz), (0, -1, 0)),
            # +X
            ((hx, -hy, hz), (hx, -hy, -hz), (hx, hy, -hz), (hx, hy, hz), (1, 0, 0)),
            # -X
            ((-hx, -hy, -hz), (-hx, -hy, hz), (-hx, hy, hz), (-hx, hy, -hz), (-1, 0, 0)),
        ]
        for a, b, c, d, n in faces:
            base = len(self.positions) // 3
            for i, p in enumerate((a, b, c, d)):
                self.positions.extend([cx + p[0], cy + p[1], cz + p[2]])
                self.normals.extend(list(n))
                self.uvs.extend([u0 + (i % 2), v0 + (0 if i < 2 else 1)])
            self.indices.extend([base, base + 1, base + 2, base, base + 2, base + 3])

    def add_cyl(self, cx, cy, cz, r_bot, r_top, h, segs=10, u0=0.0):
        base = len(self.positions) // 3
        y0, y1 = cy - h * 0.5, cy + h * 0.5
        for i in range(segs):
            a0 = 2 * math.pi * i / segs
            a1 = 2 * math.pi * (i + 1) / segs
            for a, rr, yy, vv in (
                (a0, r_bot, y0, 0.0),
                (a1, r_bot, y0, 0.0),
                (a1, r_top, y1, 1.0),
                (a0, r_top, y1, 1.0),
            ):
                x, z = math.cos(a) * rr, math.sin(a) * rr
                self.positions.extend([cx + x, yy, cz + z])
                nx, nz = math.cos(a), math.sin(a)
                self.normals.extend([nx, 0.0, nz])
                self.uvs.extend([u0 + a / (2 * math.pi), vv])
            b = base + i * 4
            self.indices.extend([b, b + 1, b + 2, b, b + 2, b + 3])

    def add_sphere(self, cx, cy, cz, r, segs=10, rings=8):
        base = len(self.positions) // 3
        for i in range(rings + 1):
            v = i / rings
            phi = math.pi * v
            for j in range(segs + 1):
                u = j / segs
                th = 2 * math.pi * u
                x = math.sin(phi) * math.cos(th)
                y = math.cos(phi)
                z = math.sin(phi) * math.sin(th)
                self.positions.extend([cx + x * r, cy + y * r, cz + z * r])
                self.normals.extend([x, y, z])
                self.uvs.extend([u, v])
        for i in range(rings):
            for j in range(segs):
                a = base + i * (segs + 1) + j
                b = a + segs + 1
                self.indices.extend([a, b, a + 1, b, b + 1, a + 1])


def pack_f32(vals: list[float]) -> bytes:
    return struct.pack(f"<{len(vals)}f", *vals)


def pack_u16(vals: list[int]) -> bytes:
    return struct.pack(f"<{len(vals)}H", *vals)


def write_glb(path: Path, parts: dict[str, MeshBuf], colors: dict[str, tuple[float, float, float]]) -> None:
    """parts keys: Skin, Cloth, Metal, Hair — each MeshBuf."""
    # Build binary blob: for each part: POSITION, NORMAL, TEXCOORD_0, INDICES
    bin_chunks: list[bytes] = []
    accessors = []
    buffer_views = []
    meshes = []
    materials = []
    nodes = []
    offset = 0

    def add_view(data: bytes, target: int | None = None) -> int:
        nonlocal offset
        # align 4
        pad = (4 - (len(data) % 4)) % 4
        data = data + b"\x00" * pad
        bv = {"buffer": 0, "byteOffset": offset, "byteLength": len(data) - pad}
        if target is not None:
            bv["target"] = target
        buffer_views.append(bv)
        bin_chunks.append(data)
        idx = len(buffer_views) - 1
        offset += len(data)
        return idx

    mat_index = {}
    for name in ("Skin", "Cloth", "Metal", "Hair", "Eye"):
        if name not in parts or not parts[name].indices:
            continue
        col = colors.get(name, (0.7, 0.7, 0.7))
        mat = {
            "name": name,
            "pbrMetallicRoughness": {
                "baseColorFactor": [col[0], col[1], col[2], 1.0],
                "metallicFactor": 0.85 if name == "Metal" else (0.05 if name == "Eye" else 0.02),
                "roughnessFactor": (
                    0.35 if name == "Metal"
                    else 0.18 if name == "Eye"
                    else 0.55 if name == "Skin"
                    else 0.75
                ),
            },
        }
        materials.append(mat)
        mat_index[name] = len(materials) - 1

        mb = parts[name]
        pos = pack_f32(mb.positions)
        nor = pack_f32(mb.normals)
        uvs = pack_f32(mb.uvs)
        ind = pack_u16(mb.indices)

        # bounds
        xs = mb.positions[0::3]
        ys = mb.positions[1::3]
        zs = mb.positions[2::3]
        pos_min = [min(xs), min(ys), min(zs)]
        pos_max = [max(xs), max(ys), max(zs)]

        bv_pos = add_view(pos, 34962)
        bv_nor = add_view(nor, 34962)
        bv_uv = add_view(uvs, 34962)
        bv_ind = add_view(ind, 34963)

        ai_pos = len(accessors)
        accessors.append({
            "bufferView": bv_pos, "componentType": 5126, "count": len(mb.positions) // 3,
            "type": "VEC3", "min": pos_min, "max": pos_max,
        })
        ai_nor = len(accessors)
        accessors.append({
            "bufferView": bv_nor, "componentType": 5126, "count": len(mb.normals) // 3, "type": "VEC3",
        })
        ai_uv = len(accessors)
        accessors.append({
            "bufferView": bv_uv, "componentType": 5126, "count": len(mb.uvs) // 2, "type": "VEC2",
        })
        ai_ind = len(accessors)
        accessors.append({
            "bufferView": bv_ind, "componentType": 5123, "count": len(mb.indices), "type": "SCALAR",
        })

        mesh_i = len(meshes)
        meshes.append({
            "name": name,
            "primitives": [{
                "attributes": {"POSITION": ai_pos, "NORMAL": ai_nor, "TEXCOORD_0": ai_uv},
                "indices": ai_ind,
                "material": mat_index[name],
            }],
        })
        nodes.append({"name": name, "mesh": mesh_i})

    blob = b"".join(bin_chunks)
    gltf = {
        "asset": {"version": "2.0", "generator": "CivilSimulator-role-bodies"},
        "buffers": [{"byteLength": len(blob)}],
        "bufferViews": buffer_views,
        "accessors": accessors,
        "materials": materials,
        "meshes": meshes,
        "nodes": list(range(len(nodes))),
        "scenes": [{"nodes": list(range(len(nodes)))}],
        "scene": 0,
    }
    # fix nodes — glTF wants node objects
    gltf["nodes"] = nodes

    json_bytes = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    json_pad = (4 - (len(json_bytes) % 4)) % 4
    json_bytes += b" " * json_pad
    bin_pad = (4 - (len(blob) % 4)) % 4
    blob += b"\x00" * bin_pad

    total = 12 + 8 + len(json_bytes) + 8 + len(blob)
    out = bytearray()
    out += struct.pack("<4sII", b"glTF", 2, total)
    out += struct.pack("<I4s", len(json_bytes), b"JSON")
    out += json_bytes
    out += struct.pack("<I4s", len(blob), b"BIN\x00")
    out += blob
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(out))


def add_facial_features(
    skin: MeshBuf, eye: MeshBuf, hair: MeshBuf,
    head_y: float, bulk: float, seed: int,
) -> None:
    """Anatomical face — eyes, brows, nose, ears (v1.4 Character Compiler baseline)."""
    hz = 0.105 * bulk
    skin.add_sphere(0, head_y + hz * 0.08, 0, hz, segs=14, rings=10)
    skin.add_sphere(0, head_y - hz * 0.55, hz * 0.35, hz * 0.72, segs=12, rings=8)
    for sx in (-1, 1):
        ex = sx * 0.038 * bulk
        skin.add_sphere(ex, head_y + 0.018, hz * 0.78, 0.016 * bulk, segs=8, rings=6)
        eye.add_sphere(ex, head_y + 0.02, hz * 0.82, 0.011 * bulk, segs=10, rings=8)
        eye.add_sphere(ex, head_y + 0.022, hz * 0.855, 0.0045 * bulk, segs=6, rings=4)
        hair.add_box(ex, head_y + 0.048, hz * 0.72, 0.028 * bulk, 0.012, 0.018)
        skin.add_sphere(ex * 1.55, head_y - 0.01, 0.02, 0.022 * bulk, segs=8, rings=6)
    skin.add_box(0, head_y - 0.008, hz * 0.92, 0.014 * bulk, 0.028, 0.016)
    skin.add_box(0, head_y - 0.038, hz * 0.86, 0.024 * bulk, 0.011, 0.008)
    topknot = (seed % 5) == 0
    if topknot:
        hair.add_sphere(0, head_y + hz * 0.95, -0.02, 0.055 * bulk, segs=10, rings=8)
        hair.add_cyl(0, head_y + hz * 0.55, -0.04, 0.018, 0.012, 0.12, segs=8)
    else:
        hair.add_box(0, head_y + hz * 0.55, -0.04, hz * 1.05, hz * 0.55, hz * 0.85)


# ---------------------------------------------------------------------------
# Role recipes — unique baked silhouettes
# ---------------------------------------------------------------------------
def build_humanoid(genre: str, role: str, seed: int) -> tuple[dict[str, MeshBuf], dict]:
    """Return (parts, colors). Proportions vary by role hash."""
    rng = (seed * 1103515245 + 12345) & 0x7FFFFFFF
    def r(a, b):
        nonlocal rng
        rng = (rng * 1103515245 + 12345) & 0x7FFFFFFF
        return a + (b - a) * (rng / 0x7FFFFFFF)

    h = r(1.62, 1.82)          # overall height scale
    bulk = r(0.88, 1.14)
    skin = MeshBuf()
    cloth = MeshBuf()
    metal = MeshBuf()
    hair = MeshBuf()
    eye = MeshBuf()

    # ---- shared anatomy (skin) — v1.4 hero-readable proportions ----
    head_y = 1.58 * h / 1.7
    add_facial_features(skin, eye, hair, head_y, bulk, seed)
    skin.add_cyl(0, head_y - 0.14, 0, 0.048, 0.052, 0.11, segs=12)
    skin.add_box(0, 1.15 * h / 1.7, 0, 0.14 * bulk, 0.32, 0.09)
    skin.add_box(0, 0.92 * h / 1.7, 0, 0.11 * bulk, 0.18, 0.07)
    arm_y = 1.2 * h / 1.7
    for sx in (-1, 1):
        skin.add_cyl(sx * 0.28 * bulk, arm_y - 0.08, 0, 0.048, 0.042, 0.28, segs=12)
        skin.add_cyl(sx * 0.28 * bulk, arm_y - 0.32, 0, 0.038, 0.034, 0.22, segs=10)
        skin.add_sphere(sx * 0.28 * bulk, arm_y - 0.46, 0, 0.042, segs=10, rings=8)
    for sx in (-1, 1):
        skin.add_cyl(sx * 0.09, 0.52, 0, 0.052, 0.046, 0.42, segs=12)
        skin.add_cyl(sx * 0.09, 0.22, 0, 0.044, 0.038, 0.38, segs=10)
        skin.add_box(sx * 0.09, 0.05, 0.05, 0.1, 0.07, 0.18)

    # ---- genre clothing (cloth / metal / hair) ----
    torso_y = 1.05 * h / 1.7
    if genre == "wuxia":
        # 劲装 + 广袖 + 披风轮廓 + 发髻
        cloth.add_box(0, torso_y, 0, 0.42 * bulk, 0.55, 0.22)  # torso
        cloth.add_box(0, torso_y - 0.35, 0, 0.38 * bulk, 0.35, 0.2)  # lower robe
        for sx in (-1, 1):
            cloth.add_box(sx * 0.38 * bulk, arm_y - 0.05, 0, 0.22, 0.12, 0.28)  # wide sleeves
        cloth.add_box(0, torso_y + 0.05, -0.14, 0.5 * bulk, 0.7, 0.06)  # cape plane
        cloth.add_box(0, torso_y - 0.05, 0.12, 0.08, 0.5, 0.04)  # sash
        hair.add_sphere(0, head_y + 0.08, -0.02, 0.12)
        hair.add_sphere(0, head_y + 0.18, -0.02, 0.07)  # topknot
        if "sword" in role or "sect" in role or "wanderer" in role or "swordsman" in role:
            metal.add_box(0.38, 0.95, 0.05, 0.03, 0.75, 0.08)
            metal.add_box(0.38, 0.55, 0.05, 0.16, 0.04, 0.06)
        if "blade" in role:
            metal.add_box(0.36, 0.9, 0.05, 0.05, 0.55, 0.1)
        if "beggar" in role or "drunk" in role:
            cloth.add_box(0, head_y + 0.12, 0, 0.5, 0.08, 0.5)  # bamboo hat brim
            cloth.add_cyl(0, head_y + 0.14, 0, 0.12, 0.1, 0.1)
        if "physician" in role:
            cloth.add_box(0, torso_y - 0.15, 0.14, 0.32, 0.45, 0.04)  # apron
        if "thief" in role or "rogue_mask" in role:
            cloth.add_box(0, head_y - 0.02, 0.1, 0.16, 0.1, 0.04)  # mask
        if "story" in role:
            cloth.add_box(0.32, 1.05, 0.1, 0.28, 0.02, 0.16)  # fan

    elif genre == "ancient":
        # 交领深衣 / 襆头 / 广袖
        cloth.add_box(0, torso_y - 0.05, 0, 0.48 * bulk, 0.85, 0.24)  # long robe
        for sx in (-1, 1):
            cloth.add_box(sx * 0.4 * bulk, arm_y, 0.02, 0.26, 0.14, 0.32)
        cloth.add_box(0, torso_y + 0.1, 0.13, 0.2, 0.35, 0.05)  # cross collar
        hair.add_sphere(0, head_y + 0.06, -0.02, 0.11)
        if "clerk" in role:
            cloth.add_box(0, head_y + 0.12, 0, 0.28, 0.1, 0.22)  # futou
            cloth.add_box(-0.2, head_y + 0.12, 0, 0.12, 0.08, 0.04)
            cloth.add_box(0.2, head_y + 0.12, 0, 0.12, 0.08, 0.04)
        elif "guard" in role:
            metal.add_box(0, torso_y + 0.05, 0, 0.45 * bulk, 0.5, 0.26)
            metal.add_sphere(0, head_y + 0.02, 0, 0.14)
            metal.add_box(0, head_y - 0.02, 0.12, 0.2, 0.08, 0.06)
        elif "archer" in role:
            cloth.add_box(0, torso_y, 0, 0.36 * bulk, 0.5, 0.2)
            cloth.add_box(0, head_y + 0.05, -0.05, 0.2, 0.16, 0.2)  # hood
            metal.add_box(-0.3, 1.0, -0.05, 0.04, 0.55, 0.04)  # bow approx
        elif "trader" in role:
            cloth.add_box(0, head_y + 0.1, 0, 0.55, 0.06, 0.55)
            cloth.add_box(0.2, torso_y - 0.1, 0.15, 0.18, 0.25, 0.12)  # pouch
        else:  # student
            hair.add_sphere(0, head_y + 0.16, -0.02, 0.06)

    elif genre == "scifi":
        # hard-surface suit / helmet / pack
        metal.add_box(0, torso_y, 0, 0.4 * bulk, 0.55, 0.24)
        metal.add_box(0, torso_y - 0.35, 0, 0.36 * bulk, 0.35, 0.22)
        for sx in (-1, 1):
            metal.add_cyl(sx * 0.28 * bulk, arm_y - 0.1, 0, 0.055, 0.05, 0.42)
            metal.add_box(sx * 0.22 * bulk, torso_y + 0.15, 0, 0.14, 0.1, 0.18)  # pauldrons
        if "engineer" in role or "xeno" in role:
            metal.add_sphere(0, head_y, 0.02, 0.13)
            metal.add_box(0, head_y, 0.12, 0.2, 0.08, 0.08)  # visor
            metal.add_box(0, torso_y, -0.2, 0.3, 0.4, 0.12)  # backpack
        elif "scout" in role:
            cloth.add_box(0, torso_y, 0, 0.36 * bulk, 0.5, 0.2)
            metal.add_box(0, head_y, 0.1, 0.22, 0.08, 0.1)
            metal.add_box(0.35, 0.95, 0.1, 0.45, 0.06, 0.08)  # rifle
        else:  # comms
            cloth.add_box(0, torso_y, 0, 0.38 * bulk, 0.52, 0.2)
            metal.add_box(0, head_y, 0.1, 0.2, 0.07, 0.1)
            metal.add_box(0.3, 1.0, 0.12, 0.12, 0.12, 0.06)  # scanner

    elif genre == "xuanhuan":
        # 西游：僧袍 / 天将甲 / 紧身 + 佛冠或束发
        if "outer" in role:
            cloth.add_box(0, torso_y - 0.05, 0, 0.5 * bulk, 0.9, 0.26)
            for sx in (-1, 1):
                cloth.add_box(sx * 0.42 * bulk, arm_y, 0, 0.28, 0.14, 0.34)
            cloth.add_box(0, torso_y + 0.05, -0.16, 0.55 * bulk, 0.85, 0.05)
            metal.add_box(0, head_y + 0.12, 0, 0.18, 0.12, 0.18)  # circlet
            hair.add_sphere(0, head_y + 0.05, -0.02, 0.12)
        elif "rogue" in role:
            cloth.add_box(0, torso_y, 0, 0.38 * bulk, 0.6, 0.2)
            cloth.add_box(0, head_y + 0.02, -0.05, 0.22, 0.2, 0.22)
            metal.add_cyl(0.34, 0.85, 0, 0.03, 0.03, 1.1)
            metal.add_sphere(0.34, 1.4, 0, 0.06)
        else:  # alchemist — 丹炉袍
            cloth.add_box(0, torso_y - 0.05, 0, 0.44 * bulk, 0.75, 0.24)
            cloth.add_box(0, torso_y - 0.1, 0.14, 0.3, 0.4, 0.05)
            hair.add_sphere(0, head_y + 0.08, -0.02, 0.1)
            metal.add_sphere(0.25, 1.15, 0.2, 0.07)  # elixir orb

    elif genre == "modern":
        # 当代：西装 / 休闲 / 工装
        cloth.add_box(0, torso_y, 0, 0.38 * bulk, 0.52, 0.2)
        cloth.add_box(0, torso_y - 0.32, 0, 0.32 * bulk, 0.38, 0.18)
        if "office" in role:
            cloth.add_box(0, torso_y + 0.08, 0.12, 0.12, 0.28, 0.04)
            cloth.add_box(0, torso_y + 0.02, -0.08, 0.42 * bulk, 0.48, 0.06)
            hair.add_sphere(0, head_y + 0.04, -0.02, 0.1)
        elif "courier" in role:
            cloth.add_box(0, torso_y + 0.05, -0.1, 0.44 * bulk, 0.55, 0.08)
            cloth.add_box(0, torso_y, -0.18, 0.28, 0.35, 0.1)
            hair.add_sphere(0, head_y + 0.02, -0.02, 0.1)
            metal.add_box(0.28, 1.0, 0.12, 0.1, 0.14, 0.06)
        else:
            cloth.add_box(0, torso_y + 0.02, 0, 0.36 * bulk, 0.48, 0.18)
            hair.add_sphere(0, head_y + 0.05, -0.02, 0.11)

    elif genre == "mystery":
        cloth.add_box(0, torso_y, 0, 0.4 * bulk, 0.55, 0.22)  # jacket
        cloth.add_box(0, torso_y - 0.35, 0, 0.34 * bulk, 0.4, 0.2)  # trousers
        cloth.add_box(0, torso_y + 0.05, -0.12, 0.55 * bulk, 0.85, 0.08)  # inverness cape
        if "detective" in role:
            cloth.add_box(0, head_y + 0.1, 0, 0.22, 0.1, 0.26)  # deerstalker crown
            cloth.add_box(0, head_y + 0.06, 0, 0.34, 0.03, 0.34)  # brim
            cloth.add_box(0, head_y + 0.14, -0.08, 0.08, 0.1, 0.12)  # ear flap
        elif "reporter" in role:
            cloth.add_box(0, head_y + 0.1, 0, 0.2, 0.1, 0.22)
            cloth.add_box(0, head_y + 0.05, 0, 0.32, 0.025, 0.32)
            hair.add_sphere(0, head_y + 0.02, -0.02, 0.11)
        else:  # doctor
            cloth.add_box(0, torso_y - 0.05, 0.12, 0.34, 0.55, 0.05)  # white coat front
            hair.add_sphere(0, head_y + 0.04, -0.02, 0.11)
        if "detective" in role:
            metal.add_box(0.32, 0.95, 0.1, 0.16, 0.05, 0.08)  # pistol

    palette = ROLE_COLORS.get(role, {})
    colors = {
        "Skin": (0.85, 0.7, 0.55),
        "Cloth": palette.get("Cloth", (0.35, 0.32, 0.3)),
        "Metal": palette.get("Metal", (0.7, 0.72, 0.75)),
        "Hair": palette.get("Hair", (0.12, 0.1, 0.1)),
        "Eye": (0.08, 0.12, 0.22),
    }
    return {"Skin": skin, "Cloth": cloth, "Metal": metal, "Hair": hair, "Eye": eye}, colors


# Baked cloth/metal/hair base colors (match characterFigures presets)
ROLE_COLORS: dict[str, dict[str, tuple[float, float, float]]] = {
    "wuxia_wanderer": {"Cloth": (0.239, 0.271, 0.329), "Metal": (0.659, 0.722, 0.784), "Hair": (0.102, 0.082, 0.125)},
    "wuxia_sect_disciple": {"Cloth": (0.957, 0.965, 0.973), "Metal": (0.369, 0.722, 0.91), "Hair": (0.059, 0.055, 0.071)},
    "wuxia_blade_rogue": {"Cloth": (0.227, 0.141, 0.063), "Metal": (0.769, 0.416, 0.165), "Hair": (0.039, 0.047, 0.063)},
    "wuxia_thief": {"Cloth": (0.118, 0.161, 0.231), "Metal": (0.133, 0.827, 0.933), "Hair": (0.067, 0.094, 0.153)},
    "wuxia_beggar": {"Cloth": (0.341, 0.325, 0.306), "Metal": (0.659, 0.635, 0.62), "Hair": (0.161, 0.145, 0.141)},
    "wuxia_storyteller": {"Cloth": (0.443, 0.247, 0.071), "Metal": (0.984, 0.749, 0.141), "Hair": (0.216, 0.255, 0.318)},
    "wuxia_physician": {"Cloth": (0.925, 0.992, 0.961), "Metal": (0.063, 0.725, 0.506), "Hair": (0.122, 0.161, 0.216)},
    "ancient_student": {"Cloth": (0.859, 0.918, 0.996), "Metal": (0.145, 0.388, 0.922), "Hair": (0.067, 0.094, 0.153)},
    "ancient_clerk": {"Cloth": (0.118, 0.227, 0.373), "Metal": (0.961, 0.62, 0.043), "Hair": (0.122, 0.161, 0.216)},
    "ancient_guard": {"Cloth": (0.471, 0.208, 0.059), "Metal": (0.988, 0.827, 0.302), "Hair": (0.11, 0.098, 0.09)},
    "ancient_archer": {"Cloth": (0.212, 0.325, 0.078), "Metal": (0.518, 0.8, 0.086), "Hair": (0.161, 0.145, 0.141)},
    "ancient_trader": {"Cloth": (0.573, 0.251, 0.055), "Metal": (0.984, 0.749, 0.141), "Hair": (0.122, 0.161, 0.216)},
    "scifi_comms": {"Cloth": (0.118, 0.227, 0.373), "Metal": (0.22, 0.741, 0.973), "Hair": (0.055, 0.647, 0.914)},
    "scifi_engineer": {"Cloth": (0.267, 0.251, 0.235), "Metal": (0.984, 0.573, 0.235), "Hair": (0.976, 0.451, 0.086)},
    "scifi_scout": {"Cloth": (0.2, 0.255, 0.333), "Metal": (0.133, 0.827, 0.933), "Hair": (0.118, 0.161, 0.231)},
    "scifi_xeno": {"Cloth": (0.192, 0.18, 0.506), "Metal": (0.655, 0.545, 0.98), "Hair": (0.486, 0.227, 0.929)},
    "xuanhuan_outer": {"Cloth": (0.878, 0.906, 1.0), "Metal": (0.506, 0.549, 0.973), "Hair": (0.067, 0.094, 0.153)},
    "xuanhuan_rogue": {"Cloth": (0.118, 0.106, 0.294), "Metal": (0.753, 0.518, 0.988), "Hair": (0.122, 0.161, 0.216)},
    "xuanhuan_alchemist": {"Cloth": (0.078, 0.325, 0.176), "Metal": (0.29, 0.871, 0.502), "Hair": (0.216, 0.255, 0.318)},
    "mystery_detective": {"Cloth": (0.11, 0.098, 0.09), "Metal": (0.659, 0.635, 0.62), "Hair": (0.122, 0.161, 0.216)},
    "mystery_reporter": {"Cloth": (0.996, 0.953, 0.78), "Metal": (0.961, 0.62, 0.043), "Hair": (0.471, 0.208, 0.059)},
    "mystery_doctor": {"Cloth": (0.973, 0.98, 0.988), "Metal": (0.055, 0.647, 0.914), "Hair": (0.216, 0.255, 0.318)},
    "modern_civilian": {"Cloth": (0.392, 0.455, 0.545), "Metal": (0.58, 0.639, 0.722), "Hair": (0.216, 0.255, 0.318)},
    "modern_office": {"Cloth": (0.118, 0.161, 0.231), "Metal": (0.659, 0.635, 0.62), "Hair": (0.122, 0.161, 0.216)},
    "modern_courier": {"Cloth": (0.984, 0.573, 0.235), "Metal": (0.22, 0.741, 0.973), "Hair": (0.067, 0.094, 0.153)},
    "enterprise_ceo": {"Cloth": (0.12, 0.12, 0.14), "Metal": (0.85, 0.75, 0.35), "Hair": (0.1, 0.09, 0.08)},
    "enterprise_cto": {"Cloth": (0.22, 0.35, 0.45), "Metal": (0.4, 0.85, 0.95), "Hair": (0.15, 0.14, 0.13)},
    "enterprise_vc": {"Cloth": (0.15, 0.18, 0.22), "Metal": (0.7, 0.7, 0.72), "Hair": (0.12, 0.11, 0.1)},
    "securities_trader": {"Cloth": (0.18, 0.28, 0.38), "Metal": (0.3, 0.75, 0.45), "Hair": (0.1, 0.1, 0.12)},
    "securities_analyst": {"Cloth": (0.25, 0.25, 0.28), "Metal": (0.75, 0.65, 0.35), "Hair": (0.12, 0.11, 0.1)},
    "securities_retailer": {"Cloth": (0.45, 0.35, 0.25), "Metal": (0.9, 0.55, 0.2), "Hair": (0.2, 0.15, 0.1)},
    "military_staff": {"Cloth": (0.25, 0.32, 0.22), "Metal": (0.55, 0.6, 0.45), "Hair": (0.1, 0.1, 0.09)},
    "military_intel": {"Cloth": (0.12, 0.14, 0.16), "Metal": (0.4, 0.55, 0.65), "Hair": (0.08, 0.08, 0.09)},
    "military_logi": {"Cloth": (0.35, 0.38, 0.28), "Metal": (0.85, 0.7, 0.25), "Hair": (0.15, 0.14, 0.12)},
    "npc_swordsman": {"Cloth": (0.945, 0.961, 0.976), "Metal": (0.22, 0.741, 0.973), "Hair": (0.067, 0.094, 0.153)},
    "npc_rogue_mask": {"Cloth": (0.094, 0.094, 0.106), "Metal": (0.937, 0.267, 0.267), "Hair": (0.094, 0.094, 0.106)},
    "npc_drunkard": {"Cloth": (0.443, 0.247, 0.071), "Metal": (0.984, 0.749, 0.141), "Hair": (0.161, 0.145, 0.141)},
    "npc_boatman": {"Cloth": (0.341, 0.325, 0.306), "Metal": (0.471, 0.443, 0.424), "Hair": (0.11, 0.098, 0.09)},
    "npc_storyteller": {"Cloth": (0.486, 0.176, 0.071), "Metal": (0.992, 0.729, 0.455), "Hair": (0.267, 0.251, 0.235)},
    "npc_default": {"Cloth": (0.392, 0.455, 0.545), "Metal": (0.58, 0.639, 0.722), "Hair": (0.216, 0.255, 0.318)},
}


ROLES = [
    # wuxia
    ("wuxia", "wuxia_wanderer"),
    ("wuxia", "wuxia_sect_disciple"),
    ("wuxia", "wuxia_blade_rogue"),
    ("wuxia", "wuxia_thief"),
    ("wuxia", "wuxia_beggar"),
    ("wuxia", "wuxia_storyteller"),
    ("wuxia", "wuxia_physician"),
    ("wuxia", "npc_swordsman"),
    ("wuxia", "npc_rogue_mask"),
    ("wuxia", "npc_drunkard"),
    ("wuxia", "npc_boatman"),
    ("wuxia", "npc_storyteller"),
    ("wuxia", "npc_default"),
    # ancient
    ("ancient", "ancient_student"),
    ("ancient", "ancient_clerk"),
    ("ancient", "ancient_guard"),
    ("ancient", "ancient_archer"),
    ("ancient", "ancient_trader"),
    # scifi
    ("scifi", "scifi_comms"),
    ("scifi", "scifi_engineer"),
    ("scifi", "scifi_scout"),
    ("scifi", "scifi_xeno"),
    # xuanhuan
    ("xuanhuan", "xuanhuan_outer"),
    ("xuanhuan", "xuanhuan_rogue"),
    ("xuanhuan", "xuanhuan_alchemist"),
    # mystery
    ("mystery", "mystery_detective"),
    ("mystery", "mystery_reporter"),
    ("mystery", "mystery_doctor"),
    # modern
    ("modern", "modern_civilian"),
    ("modern", "modern_office"),
    ("modern", "modern_courier"),
    # enterprise / securities / military (reuse modern/scifi silhouettes)
    ("modern", "enterprise_ceo"),
    ("modern", "enterprise_cto"),
    ("modern", "enterprise_vc"),
    ("modern", "securities_trader"),
    ("modern", "securities_analyst"),
    ("modern", "securities_retailer"),
    ("scifi", "military_staff"),
    ("scifi", "military_intel"),
    ("scifi", "military_logi"),
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    catalog = []
    for i, (genre, role_id) in enumerate(ROLES):
        role_dir = OUT / role_id
        parts, colors = build_humanoid(genre, role_id, seed=1000 + i * 97)
        glb_path = role_dir / "body.glb"
        write_glb(glb_path, parts, colors)
        for skin in SKIN_NAMES:
            gen_skin_pack(role_dir, skin)
        catalog.append({
            "id": role_id,
            "genre": genre,
            "body": f"/models/characters/roles/{role_id}/body.glb",
            "skins": [
                {
                    "id": s,
                    "map": f"/models/characters/roles/{role_id}/skins/{s}/albedo.png",
                    "roughnessMap": f"/models/characters/roles/{role_id}/skins/{s}/roughness.png",
                    "normalMap": f"/models/characters/roles/{role_id}/skins/{s}/normal.png",
                    "metalnessMap": f"/models/characters/roles/{role_id}/skins/{s}/metalness.png",
                }
                for s in SKIN_NAMES
            ],
        })
        print(f"ok {role_id}")
    (OUT / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(catalog)} unique bodies → {OUT}")


if __name__ == "__main__":
    main()
