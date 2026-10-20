#!/usr/bin/env python3
"""Size + AABB aspect gate for hy3d NPC bodies before frontend enablement."""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROLES = [
    "ancient_student",
    "ancient_clerk",
    "ancient_guard",
    "ancient_archer",
    "ancient_trader",
    "ancient_farmer",
    "ancient_porter",
    "ancient_artisan",
]
MIN_BYTES = 400_000
# height / max(width, depth) — reject paper-flat slabs
MIN_ASPECT = 1.35
MAX_ASPECT = 3.2


def _glb_accessor_bounds(path: Path) -> tuple[float, float, float] | None:
    """Best-effort: read first POSITION accessor min/max from GLB JSON chunk."""
    data = path.read_bytes()
    if len(data) < 20 or data[:4] != b"glTF":
        return None
    # GLB: 12-byte header, then JSON chunk
    total_len = struct.unpack_from("<I", data, 8)[0]
    if total_len > len(data):
        return None
    chunk_len, chunk_type = struct.unpack_from("<II", data, 12)
    if chunk_type != 0x4E4F534A:  # JSON
        return None
    js = data[20:20 + chunk_len]
    try:
        gltf = json.loads(js)
    except Exception:
        return None
    accessors = gltf.get("accessors") or []
    for acc in accessors:
        if acc.get("type") != "VEC3":
            continue
        mn, mx = acc.get("min"), acc.get("max")
        if not (isinstance(mn, list) and isinstance(mx, list) and len(mn) == 3 and len(mx) == 3):
            continue
        dx = float(mx[0]) - float(mn[0])
        dy = float(mx[1]) - float(mn[1])
        dz = float(mx[2]) - float(mn[2])
        # assume Y-up humanoid
        h = max(dx, dy, dz)
        w = sorted([dx, dy, dz])[1]  # median axis as thickness proxy
        if w <= 1e-6:
            continue
        return h, w, h / w
    return None


def main() -> int:
    report = []
    ok = True
    for rid in ROLES:
        p = ROOT / "frontend/public/models/characters/roles" / rid / "hy3d" / "body.glb"
        entry: dict = {"id": rid, "path": str(p.relative_to(ROOT))}
        if not p.is_file():
            entry.update(pass_=False, reason="missing")
            ok = False
            report.append(entry)
            continue
        size = p.stat().st_size
        entry["bytes"] = size
        if size < MIN_BYTES:
            entry.update(pass_=False, reason=f"bytes<{MIN_BYTES}")
            ok = False
            report.append(entry)
            continue
        bounds = _glb_accessor_bounds(p)
        if bounds:
            h, w, aspect = bounds
            entry.update(height=round(h, 4), width=round(w, 4), aspect=round(aspect, 3))
            if not (MIN_ASPECT <= aspect <= MAX_ASPECT):
                entry.update(pass_=False, reason=f"aspect={aspect:.2f} not in [{MIN_ASPECT},{MAX_ASPECT}]")
                ok = False
                report.append(entry)
                continue
        else:
            entry["aspect"] = None
            entry["note"] = "no POSITION bounds; size-only gate"
        entry["pass_"] = True
        report.append(entry)

    out = ROOT / "backend/data/runtime/generator/hy3d_npc/gate_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    # JSON-friendly key
    serial = []
    for e in report:
        e2 = dict(e)
        e2["pass"] = e2.pop("pass_", False)
        serial.append(e2)
    out.write_text(json.dumps({"ok": ok, "roles": serial}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for e in serial:
        flag = "PASS" if e["pass"] else "FAIL"
        print(f"{flag} {e['id']}: {e.get('reason') or e.get('bytes')} aspect={e.get('aspect')}")
    print(f"report {out}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
