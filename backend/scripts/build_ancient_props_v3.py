#!/usr/bin/env python3
"""Ancient street props v3 — name-matched silhouettes + baked albedo textures.

Each GLB is recognizably the Chinese object named in PROP_CATALOG (灯笼≠酒坛).
Textures: wood grain / stone / fabric / glaze baked as PNG into the GLB.
"""
from __future__ import annotations

import json
import math
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "frontend/public/models/props/ancient"

# kind → Chinese display name (must match map props[].name)
PROP_CATALOG = {
    "lantern": "灯笼",
    "banner": "酒旗",
    "table": "八仙桌",
    "stool": "板凳",
    "well": "水井",
    "stone_lion": "石狮",
    "crate": "货箱",
    "wine_jar": "酒坛",
    "bench": "石凳",
    "flower_pot": "花盆",
    "cart": "板车",
}


def pad4(n: int) -> int:
    return (4 - (n % 4)) % 4


def png_rgba(w: int, h: int, pixels: list[tuple[int, int, int, int]]) -> bytes:
    """Minimal RGBA PNG writer."""
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = bytearray()
    for y in range(h):
        raw.append(0)
        for x in range(w):
            raw.extend(pixels[y * w + x])
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def tex_wood(seed: int = 1) -> bytes:
    w = h = 64
    px = []
    for y in range(h):
        for x in range(w):
            n = ((x * 17 + y * 3 + seed * 11) % 23) / 23
            g = int(90 + 40 * n + 20 * math.sin(y * 0.4 + seed))
            r = int(g * 1.15)
            b = int(g * 0.55)
            # grain lines
            if (x + int(3 * math.sin(y * 0.2))) % 9 == 0:
                r, g, b = int(r * 0.7), int(g * 0.7), int(b * 0.7)
            px.append((min(255, r), min(255, g), min(255, b), 255))
    return png_rgba(w, h, px)


def tex_stone(seed: int = 2) -> bytes:
    w = h = 64
    px = []
    for y in range(h):
        for x in range(w):
            n = ((x * 13 ^ y * 7 ^ seed * 5) % 31) / 31
            v = int(120 + 50 * n)
            # mortar grid
            if x % 16 < 1 or y % 12 < 1:
                v = int(v * 0.65)
            px.append((v, v - 4, v - 10, 255))
    return png_rgba(w, h, px)


def tex_cloth(seed: int = 3, rgb=(180, 40, 40)) -> bytes:
    w = h = 64
    px = []
    for y in range(h):
        for x in range(w):
            weave = 0.85 + 0.15 * (((x // 2) + (y // 2) + seed) % 2)
            # emblem cross
            emblem = abs(x - 32) < 3 or abs(y - 32) < 3
            r = int(rgb[0] * weave * (0.7 if emblem else 1))
            g = int(rgb[1] * weave * (0.7 if emblem else 1))
            b = int(rgb[2] * weave)
            px.append((r, g, b, 255))
    return png_rgba(w, h, px)


def tex_paper() -> bytes:
    w = h = 64
    px = []
    for y in range(h):
        for x in range(w):
            v = 220 + ((x * y) % 17)
            px.append((min(255, v), min(255, v - 8), min(255, v - 20), 255))
    return png_rgba(w, h, px)


def tex_glaze() -> bytes:
    w = h = 64
    px = []
    for y in range(h):
        for x in range(w):
            band = (y // 8) % 2
            r = 40 + band * 20
            g = 70 + band * 30
            b = 55 + int(20 * math.sin(x * 0.3))
            px.append((r, g, b, 255))
    return png_rgba(w, h, px)


def tex_leaf() -> bytes:
    w = h = 32
    px = []
    for y in range(h):
        for x in range(w):
            d = math.hypot(x - 16, y - 16) / 16
            g = int(40 + 80 * (1 - min(1, d)))
            px.append((30, g, 25, 255))
    return png_rgba(w, h, px)


class TexMesh:
    """Multi-material mesh with UVs; one texture image per material part."""

    def __init__(self):
        self.parts: list[dict] = []

    def _part(self, rgba, png: bytes | None, metal=0.05, rough=0.75):
        key = (tuple(rgba), id(png))
        for p in self.parts:
            if p["_key"] == key:
                return p
        p = {
            "_key": key,
            "positions": [], "normals": [], "uvs": [], "indices": [],
            "rgba": list(rgba), "png": png, "metal": metal, "rough": rough,
        }
        self.parts.append(p)
        return p

    def box(self, cx, cy, cz, sx, sy, sz, rgba, png=None, metal=0.05, rough=0.75):
        hx, hy, hz = sx / 2, sy / 2, sz / 2
        # 6 faces with unique verts + UVs
        faces = [
            # +Z, -Z, +X, -X, +Y, -Y
            ([( -hx, -hy,  hz), ( hx, -hy,  hz), ( hx,  hy,  hz), (-hx,  hy,  hz)], (0, 0, 1)),
            ([( hx, -hy, -hz), (-hx, -hy, -hz), (-hx,  hy, -hz), ( hx,  hy, -hz)], (0, 0, -1)),
            ([( hx, -hy,  hz), ( hx, -hy, -hz), ( hx,  hy, -hz), ( hx,  hy,  hz)], (1, 0, 0)),
            ([(-hx, -hy, -hz), (-hx, -hy,  hz), (-hx,  hy,  hz), (-hx,  hy, -hz)], (-1, 0, 0)),
            ([(-hx,  hy,  hz), ( hx,  hy,  hz), ( hx,  hy, -hz), (-hx,  hy, -hz)], (0, 1, 0)),
            ([(-hx, -hy, -hz), ( hx, -hy, -hz), ( hx, -hy,  hz), (-hx, -hy,  hz)], (0, -1, 0)),
        ]
        uvs_face = [(0, 0), (1, 0), (1, 1), (0, 1)]
        p = self._part(rgba, png, metal, rough)
        for corners, n in faces:
            base = len(p["positions"]) // 3
            for (lx, ly, lz), (u, v) in zip(corners, uvs_face):
                p["positions"].extend([cx + lx, cy + ly, cz + lz])
                p["normals"].extend(list(n))
                p["uvs"].extend([u, v])
            p["indices"].extend([base, base + 1, base + 2, base, base + 2, base + 3])

    def cyl(self, cx, cy, cz, r_bot, r_top, h, segs, rgba, png=None, metal=0.05, rough=0.7):
        p = self._part(rgba, png, metal, rough)
        for i in range(segs):
            a0 = 2 * math.pi * i / segs
            a1 = 2 * math.pi * (i + 1) / segs
            x0, z0 = math.cos(a0), math.sin(a0)
            x1, z1 = math.cos(a1), math.sin(a1)
            base = len(p["positions"]) // 3
            verts = [
                (cx + r_bot * x0, cy, cz + r_bot * z0),
                (cx + r_bot * x1, cy, cz + r_bot * z1),
                (cx + r_top * x1, cy + h, cz + r_top * z1),
                (cx + r_top * x0, cy + h, cz + r_top * z0),
            ]
            nx, nz = (x0 + x1) * 0.5, (z0 + z1) * 0.5
            ln = math.hypot(nx, nz) or 1
            n = (nx / ln, 0, nz / ln)
            u0, u1 = i / segs, (i + 1) / segs
            for (x, y, z), (u, v) in zip(verts, [(u0, 0), (u1, 0), (u1, 1), (u0, 1)]):
                p["positions"].extend([x, y, z])
                p["normals"].extend(list(n))
                p["uvs"].extend([u, v])
            p["indices"].extend([base, base + 1, base + 2, base, base + 2, base + 3])

    def save(self, path: Path):
        import array
        blob = bytearray()
        accessors, buffer_views, materials, primitives, images, textures, samplers = [], [], [], [], [], [], []
        samplers.append({"magFilter": 9729, "minFilter": 9729, "wrapS": 10497, "wrapT": 10497})

        def align():
            while len(blob) % 4:
                blob.append(0)

        for pi, part in enumerate(self.parts):
            if not part["indices"]:
                continue
            pos = array.array("f", part["positions"])
            nor = array.array("f", part["normals"])
            uvs = array.array("f", part["uvs"])
            idx = array.array("H", part["indices"]) if max(part["indices"]) < 65535 else array.array("I", part["indices"])

            pos_off = len(blob); blob.extend(pos.tobytes()); align()
            nor_off = len(blob); blob.extend(nor.tobytes()); align()
            uv_off = len(blob); blob.extend(uvs.tobytes()); align()
            idx_off = len(blob); blob.extend(idx.tobytes()); align()

            nvert = len(part["positions"]) // 3
            xs, ys, zs = part["positions"][0::3], part["positions"][1::3], part["positions"][2::3]
            ai = len(accessors)
            bv0 = len(buffer_views)
            accessors.extend([
                {"bufferView": bv0, "componentType": 5126, "count": nvert, "type": "VEC3",
                 "min": [min(xs), min(ys), min(zs)], "max": [max(xs), max(ys), max(zs)]},
                {"bufferView": bv0 + 1, "componentType": 5126, "count": nvert, "type": "VEC3"},
                {"bufferView": bv0 + 2, "componentType": 5126, "count": nvert, "type": "VEC2"},
                {"bufferView": bv0 + 3, "componentType": 5123 if idx.typecode == "H" else 5125,
                 "count": len(part["indices"]), "type": "SCALAR"},
            ])
            buffer_views.extend([
                {"buffer": 0, "byteOffset": pos_off, "byteLength": nvert * 12},
                {"buffer": 0, "byteOffset": nor_off, "byteLength": nvert * 12},
                {"buffer": 0, "byteOffset": uv_off, "byteLength": nvert * 8},
                {"buffer": 0, "byteOffset": idx_off, "byteLength": len(idx) * idx.itemsize},
            ])
            mat = {
                "name": f"mat_{pi}",
                "pbrMetallicRoughness": {
                    "baseColorFactor": part["rgba"],
                    "metallicFactor": part["metal"],
                    "roughnessFactor": part["rough"],
                },
                "doubleSided": True,
            }
            if part["png"]:
                img_off = len(blob)
                blob.extend(part["png"]); align()
                ii = len(images)
                images.append({"mimeType": "image/png", "bufferView": len(buffer_views)})
                buffer_views.append({"buffer": 0, "byteOffset": img_off, "byteLength": len(part["png"])})
                ti = len(textures)
                textures.append({"sampler": 0, "source": ii})
                mat["pbrMetallicRoughness"]["baseColorTexture"] = {"index": ti}
                mat["pbrMetallicRoughness"]["baseColorFactor"] = [1, 1, 1, 1]
            mi = len(materials)
            materials.append(mat)
            primitives.append({
                "attributes": {"POSITION": ai, "NORMAL": ai + 1, "TEXCOORD_0": ai + 2},
                "indices": ai + 3,
                "material": mi,
            })

        js = {
            "asset": {"version": "2.0", "generator": "civsim-props-v3"},
            "scenes": [{"nodes": [0]}], "scene": 0,
            "nodes": [{"mesh": 0, "name": path.stem}],
            "meshes": [{"name": path.stem, "primitives": primitives}],
            "materials": materials,
            "accessors": accessors,
            "bufferViews": buffer_views,
            "buffers": [{"byteLength": len(blob)}],
            "samplers": samplers,
        }
        if images:
            js["images"] = images
            js["textures"] = textures
        jb = json.dumps(js, separators=(",", ":")).encode()
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


# ---- Prop builders (silhouette must read as the named object) ----

WOOD = (0.55, 0.38, 0.22, 1.0)
STONE = (0.62, 0.60, 0.56, 1.0)
RED = (0.72, 0.12, 0.12, 1.0)
GOLD = (0.78, 0.58, 0.22, 1.0)
CLAY = (0.55, 0.42, 0.30, 1.0)


def make_lantern(path: Path):
    """宫灯：木架 + 纱纸灯罩 + 流苏，绝不是方盒子。"""
    m = TexMesh()
    wood, paper = tex_wood(1), tex_paper()
    m.cyl(0, 0, 0, 0.04, 0.04, 1.55, 10, WOOD, wood)  # pole
    m.box(0, 1.55, 0, 0.55, 0.08, 0.55, WOOD, wood)  # top frame
    m.box(0, 2.05, 0, 0.55, 0.08, 0.55, WOOD, wood)  # bottom frame of shade
    # paper shade panels (taller hex-ish)
    m.cyl(0, 1.55, 0, 0.28, 0.28, 0.5, 8, (0.95, 0.9, 0.7, 1), paper, metal=0.0, rough=0.55)
    m.box(0, 2.2, 0, 0.2, 0.12, 0.2, GOLD, None, metal=0.6, rough=0.35)  # finial
    # tassels
    for a in (0, 2.1, 4.2):
        m.cyl(0.22 * math.cos(a), 1.45, 0.22 * math.sin(a), 0.015, 0.01, 0.35, 6, RED, tex_cloth(1))
    m.save(path)


def make_banner(path: Path):
    """酒旗：旗杆 + 横挑 + 长条红布旗，带布纹字带。"""
    m = TexMesh()
    wood, cloth = tex_wood(2), tex_cloth(2, (190, 30, 30))
    m.cyl(0, 0, 0, 0.05, 0.05, 2.6, 10, WOOD, wood)
    m.box(0.45, 2.35, 0, 0.9, 0.06, 0.06, WOOD, wood)  # arm
    m.box(0.85, 1.55, 0, 0.55, 1.5, 0.04, RED, cloth)  # hanging flag
    m.box(0.85, 2.25, 0, 0.5, 0.12, 0.05, GOLD, None, metal=0.5, rough=0.4)  # header
    m.save(path)


def make_table(path: Path):
    """八仙桌：方桌面 + 四腿 + 牙板，不是扁方块。"""
    m = TexMesh()
    wood = tex_wood(3)
    m.box(0, 0.78, 0, 1.35, 0.07, 1.35, WOOD, wood)  # top
    m.box(0, 0.55, 0, 1.15, 0.06, 1.15, WOOD, wood)  # apron
    for sx, sz in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        m.cyl(sx * 0.52, 0, sz * 0.52, 0.05, 0.045, 0.78, 8, WOOD, wood)
    m.save(path)


def make_stool(path: Path):
    """板凳：长条凳面 + 两端腿。"""
    m = TexMesh()
    wood = tex_wood(4)
    m.box(0, 0.42, 0, 0.95, 0.07, 0.28, WOOD, wood)
    m.box(-0.38, 0.2, 0, 0.08, 0.4, 0.22, WOOD, wood)
    m.box(0.38, 0.2, 0, 0.08, 0.4, 0.22, WOOD, wood)
    m.save(path)


def make_well(path: Path):
    """水井：石井圈 + 辘轳架 + 吊桶。"""
    m = TexMesh()
    stone, wood = tex_stone(1), tex_wood(5)
    m.cyl(0, 0, 0, 0.75, 0.7, 0.85, 16, STONE, stone)
    m.cyl(0, 0.85, 0, 0.55, 0.55, 0.12, 16, WOOD, wood)  # rim wood
    m.cyl(-0.55, 0.9, 0, 0.05, 0.05, 1.0, 8, WOOD, wood)
    m.cyl(0.55, 0.9, 0, 0.05, 0.05, 1.0, 8, WOOD, wood)
    m.cyl(0, 1.85, 0, 0.06, 0.06, 1.2, 8, WOOD, wood)  # windlass beam horizontal via thin box
    m.box(0, 1.9, 0, 1.2, 0.08, 0.08, WOOD, wood)
    m.cyl(0, 1.55, 0, 0.12, 0.1, 0.25, 8, WOOD, wood)  # bucket
    m.save(path)


def make_stone_lion(path: Path):
    """石狮：基座 + 蹲姿狮身 + 头，可读出瑞兽轮廓。"""
    m = TexMesh()
    stone = tex_stone(2)
    m.box(0, 0.22, 0, 0.85, 0.44, 0.7, STONE, stone)  # plinth
    m.box(0, 0.7, -0.05, 0.55, 0.55, 0.5, STONE, stone)  # body
    m.box(0, 1.15, 0.18, 0.42, 0.38, 0.42, STONE, stone)  # head
    m.box(0, 1.35, 0.35, 0.2, 0.12, 0.15, STONE, stone)  # snout
    m.box(-0.18, 1.28, 0.05, 0.08, 0.18, 0.08, STONE, stone)  # ear
    m.box(0.18, 1.28, 0.05, 0.08, 0.18, 0.08, STONE, stone)
    m.box(0.28, 0.55, -0.25, 0.12, 0.12, 0.35, STONE, stone)  # curled tail
    m.save(path)


def make_crate(path: Path):
    """货箱：木箱 + 铁箍 + 盖缝。"""
    m = TexMesh()
    wood = tex_wood(6)
    m.box(0, 0.4, 0, 0.85, 0.8, 0.7, WOOD, wood)
    m.box(0, 0.4, 0.36, 0.88, 0.08, 0.04, GOLD, None, metal=0.7, rough=0.4)
    m.box(0, 0.4, -0.36, 0.88, 0.08, 0.04, GOLD, None, metal=0.7, rough=0.4)
    m.box(0, 0.82, 0, 0.88, 0.05, 0.72, WOOD, wood)
    m.save(path)


def make_wine_jar(path: Path):
    """酒坛：鼓腹陶坛 + 釉带 + 封口泥头。"""
    m = TexMesh()
    glaze = tex_glaze()
    m.cyl(0, 0, 0, 0.22, 0.32, 0.35, 14, CLAY, glaze)
    m.cyl(0, 0.35, 0, 0.32, 0.28, 0.4, 14, CLAY, glaze)
    m.cyl(0, 0.75, 0, 0.18, 0.14, 0.18, 12, CLAY, glaze)
    m.box(0, 0.95, 0, 0.22, 0.08, 0.22, (0.45, 0.35, 0.25, 1), tex_wood(7))  # seal
    m.save(path)


def make_bench(path: Path):
    """石凳：弧面石条凳。"""
    m = TexMesh()
    stone = tex_stone(3)
    m.box(0, 0.4, 0, 1.5, 0.12, 0.42, STONE, stone)
    m.box(-0.55, 0.18, 0, 0.18, 0.36, 0.38, STONE, stone)
    m.box(0.55, 0.18, 0, 0.18, 0.36, 0.38, STONE, stone)
    m.save(path)


def make_flower_pot(path: Path):
    """花盆：陶盆 + 绿植团。"""
    m = TexMesh()
    glaze, leaf = tex_glaze(), tex_leaf()
    m.cyl(0, 0, 0, 0.18, 0.22, 0.35, 12, CLAY, glaze)
    m.cyl(0, 0.35, 0, 0.2, 0.12, 0.08, 12, (0.35, 0.25, 0.15, 1), tex_wood(8))
    m.cyl(0, 0.4, 0, 0.08, 0.22, 0.35, 10, (0.2, 0.45, 0.18, 1), leaf)
    m.save(path)


def make_cart(path: Path):
    """板车：车厢 + 双轮 + 车辕。"""
    m = TexMesh()
    wood = tex_wood(9)
    m.box(0, 0.55, 0, 1.5, 0.55, 0.85, WOOD, wood)  # bed
    m.box(0, 0.9, 0.4, 1.5, 0.35, 0.06, WOOD, wood)  # side
    m.box(0, 0.9, -0.4, 1.5, 0.35, 0.06, WOOD, wood)
    # wheels
    for sz in (-1, 1):
        m.cyl(0.35, 0.28, sz * 0.55, 0.28, 0.28, 0.08, 12, WOOD, wood)
    m.box(-1.1, 0.55, 0, 0.7, 0.06, 0.08, WOOD, wood)  # shaft
    m.save(path)


BUILDERS = {
    "lantern": make_lantern,
    "banner": make_banner,
    "table": make_table,
    "stool": make_stool,
    "well": make_well,
    "stone_lion": make_stone_lion,
    "crate": make_crate,
    "wine_jar": make_wine_jar,
    "bench": make_bench,
    "flower_pot": make_flower_pot,
    "cart": make_cart,
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    catalog = {}
    for kind, fn in BUILDERS.items():
        path = OUT / f"{kind}.glb"
        fn(path)
        catalog[kind] = {"name": PROP_CATALOG[kind], "file": path.name, "bytes": path.stat().st_size}
        print(f"  {PROP_CATALOG[kind]:4} → {path.name} ({path.stat().st_size} B)")
    (OUT / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ok props v3 →", OUT)


if __name__ == "__main__":
    main()
