#!/usr/bin/env python3
"""Generate ancient map 3D assets via HunyuanDiT → Hunyuan3D mesh.

Outputs GLBs under:
  frontend/public/models/buildings/ancient/hy3d/
  frontend/public/models/props/ancient/hy3d/
  frontend/public/models/stalls/ancient/hy3d/

Usage:
  backend/.venv/bin/python backend/scripts/generate_ancient_hy3d_assets.py
  backend/.venv/bin/python backend/scripts/generate_ancient_hy3d_assets.py --only landmark_tavern,lantern
  backend/.venv/bin/python backend/scripts/generate_ancient_hy3d_assets.py --priority   # landmarks + stalls first
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.generator import hunyuan_client  # noqa: E402
from app.generator.text_to_image_lite import render_reference_png  # noqa: E402
from app.config import get_settings  # noqa: E402


def _ref_image(prompt: str, *, mode: str, kind: str = "prop") -> bytes:
    """Map assets: structured lite ref (fast) → Hunyuan3D mesh. Optional dit."""
    ref_kind = "building" if kind == "building" else ("stall" if kind == "stall" else "prop")
    if mode == "dit":
        from app.generator.text_to_image import text_to_image_bytes
        return text_to_image_bytes(prompt, kind="prop" if ref_kind != "building" else "prop")
    return render_reference_png(prompt, kind=ref_kind)

OUT_BLD = ROOT / "frontend/public/models/buildings/ancient/hy3d"
OUT_PROP = ROOT / "frontend/public/models/props/ancient/hy3d"
OUT_STALL = ROOT / "frontend/public/models/stalls/ancient/hy3d"
MANIFEST = ROOT / "frontend/public/models/buildings/ancient/hy3d/manifest.json"
READY = ROOT / "frontend/public/models/hy3d_ready.json"
RUNTIME = ROOT / "backend/data/runtime/generator/hy3d_ancient"

# kind: building | prop | stall
# prompt tuned for single-object game asset, Tang/Chang'an style, clean background
ASSETS: list[dict] = [
    # —— Landmarks ——
    {
        "id": "landmark_tavern",
        "kind": "building",
        "file": "landmark_tavern.glb",
        "priority": 1,
        "prompt": (
            "highly detailed full 3D Tang dynasty two-storey wine house 醉仙楼 as a volumetric building, "
            "open front doorway showing interior counter, wooden pillars, red hanging banners, "
            "curved grey-green tile roof with upturned eaves, second-floor balcony with lattice windows, "
            "game-ready architecture asset, centered, plain white background, no people, no ground plane, "
            "not a flat relief, complete solid building from all angles"
        ),
    },
    {
        "id": "landmark_palace",
        "kind": "building",
        "file": "landmark_palace.glb",
        "priority": 1,
        "prompt": (
            "highly detailed full 3D Tang dynasty imperial palace hall 紫宸殿, tall vermilion columns, "
            "raised white marble platform with stairs, triple-tier golden glazed tile roofs, "
            "chiwen ridge ornaments, open central doorway, game-ready volumetric architecture, "
            "centered, plain white background, no people, not a flat relief"
        ),
    },
    {
        "id": "landmark_temple",
        "kind": "building",
        "file": "landmark_temple.glb",
        "priority": 1,
        "prompt": (
            "highly detailed full 3D Tang mountain Daoist temple 终南古观, grey tile hip roof, "
            "timber frame with open lattice doors, stone incense burner and lanterns in front, "
            "mountain shrine silhouette different from palace or tavern, game-ready volumetric building, "
            "centered, plain white background, no people, not a flat relief"
        ),
    },
    # —— Town / rural buildings ——
    {
        "id": "residential_a",
        "kind": "building",
        "file": "residential_a.glb",
        "priority": 2,
        "prompt": "single Tang courtyard town house, white walls dark wood beams, grey tile hip roof, game asset, white background, no people",
    },
    {
        "id": "residential_b",
        "kind": "building",
        "file": "residential_b.glb",
        "priority": 2,
        "prompt": "single Tang dynasty narrow shop-house with wooden latticed windows, grey roof, game asset, white background",
    },
    {
        "id": "residential_c",
        "kind": "building",
        "file": "residential_c.glb",
        "priority": 2,
        "prompt": "single two-storey Tang residential building with porch and red door, game asset, white background",
    },
    {
        "id": "residential_d",
        "kind": "building",
        "file": "residential_d.glb",
        "priority": 2,
        "prompt": "single Tang dynasty wing courtyard house with side wing, grey tiles, game asset, white background",
    },
    {
        "id": "farmhouse_a",
        "kind": "building",
        "file": "farmhouse_a.glb",
        "priority": 2,
        "prompt": "single rural Tang farmhouse with thatched roof, clay walls, hay stack beside, game asset, white background, no people",
    },
    {
        "id": "farmhouse_b",
        "kind": "building",
        "file": "farmhouse_b.glb",
        "priority": 2,
        "prompt": "single rustic Chinese village cottage thatch roof lean-to shed, game asset, white background",
    },
    {
        "id": "commercial_a",
        "kind": "building",
        "file": "commercial_a.glb",
        "priority": 2,
        "prompt": "single Tang market shop facade with wooden counter and shop signboard, grey tile roof, game asset, white background",
    },
    {
        "id": "shop",
        "kind": "building",
        "file": "shop.glb",
        "priority": 2,
        "prompt": "single small Tang dynasty street shop with open front and hanging cloth sign, game asset, white background",
    },
    {
        "id": "tower_gate",
        "kind": "building",
        "file": "tower_a.glb",
        "priority": 2,
        "prompt": "single Tang city gate tower 城门楼 with arched gateway and battlements, game asset, white background, no people",
    },
    {
        "id": "dock",
        "kind": "building",
        "file": "dock.glb",
        "priority": 2,
        "prompt": "single wooden river pier dock with posts and plank deck Tang China, game asset, white background, no boats",
    },
    # —— Stalls (named goods) ——
    {
        "id": "stall_fruit",
        "kind": "stall",
        "file": "stall_fruit.glb",
        "priority": 1,
        "prompt": (
            "single Tang market fruit stall with wooden table, woven baskets of peaches oranges and melons, "
            "striped awning, game asset, white background, no people"
        ),
    },
    {
        "id": "stall_cloth",
        "kind": "stall",
        "file": "stall_cloth.glb",
        "priority": 1,
        "prompt": (
            "single Tang cloth merchant stall with colorful silk fabric bolts rolled on table under blue awning, "
            "game asset, white background, no people"
        ),
    },
    {
        "id": "stall_book",
        "kind": "stall",
        "file": "stall_book.glb",
        "priority": 1,
        "prompt": (
            "single Tang book stall with stacked thread-bound books and scrolls on wooden table, brown awning, "
            "game asset, white background, no people"
        ),
    },
    {
        "id": "stall_bing",
        "kind": "stall",
        "file": "stall_bing.glb",
        "priority": 1,
        "prompt": (
            "single Tang street food stall selling flatbread 胡饼 on wooden board under orange awning, "
            "game asset, white background, no people"
        ),
    },
    {
        "id": "stall_wine",
        "kind": "stall",
        "file": "stall_wine.glb",
        "priority": 1,
        "prompt": (
            "single Tang wine stall with clay wine jars and red hanging banner under awning, "
            "game asset, white background, no people"
        ),
    },
    {
        "id": "stall_spice",
        "kind": "stall",
        "file": "stall_spice.glb",
        "priority": 1,
        "prompt": (
            "single Tang spice stall with jars and spice mounds of orange brown powders under awning, "
            "game asset, white background, no people"
        ),
    },
    # —— Street props ——
    {
        "id": "lantern",
        "kind": "prop",
        "file": "lantern.glb",
        "priority": 1,
        "prompt": "single Tang dynasty street lantern on wooden pole with glowing paper lamp, game prop asset, white background",
    },
    {
        "id": "banner",
        "kind": "prop",
        "file": "banner.glb",
        "priority": 1,
        "prompt": "single Tang red vertical shop banner hanging on wooden pole, game prop, white background",
    },
    {
        "id": "wine_jar",
        "kind": "prop",
        "file": "wine_jar.glb",
        "priority": 1,
        "prompt": "single large brown clay Chinese wine jar with rope handle, game prop asset, white background",
    },
    {
        "id": "stone_lion",
        "kind": "prop",
        "file": "stone_lion.glb",
        "priority": 1,
        "prompt": "single Chinese stone guardian lion statue on pedestal, carved detail, game prop, white background",
    },
    {
        "id": "well",
        "kind": "prop",
        "file": "well.glb",
        "priority": 1,
        "prompt": "single Tang stone water well with wooden winch frame and bucket, game prop, white background",
    },
]


def out_dir_for(kind: str) -> Path:
    if kind == "prop":
        return OUT_PROP
    if kind == "stall":
        return OUT_STALL
    return OUT_BLD


def load_manifest() -> dict:
    if MANIFEST.is_file():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {"version": 1, "engine": "hunyuan3d", "assets": {}}


def save_manifest(m: dict) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_ready_json()


def write_ready_json() -> None:
    """Frontend reads this to enable /hy3d/ URLs only for files that exist."""
    def listed(d: Path) -> list[str]:
        if not d.is_dir():
            return []
        return sorted(p.name for p in d.glob("*.glb") if p.stat().st_size > 800)

    payload = {
        "engine": "hunyuan3d",
        "buildings": listed(OUT_BLD),
        "stalls": listed(OUT_STALL),
        "props": listed(OUT_PROP),
        "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    READY.parent.mkdir(parents=True, exist_ok=True)
    READY.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def generate_one(asset: dict, *, with_texture: bool, force: bool, ref_mode: str) -> dict:
    kind = asset["kind"]
    out = out_dir_for(kind) / asset["file"]
    if out.is_file() and out.stat().st_size > 800 and not force:
        return {"id": asset["id"], "status": "skip", "path": str(out.relative_to(ROOT))}

    status = hunyuan_client.check_status(timeout=5.0)
    if not status.get("online"):
        raise SystemExit(f"Hunyuan3D offline: {status.get('message')} — start ./backend/scripts/hunyuan3d/start_server.sh")

    print(f"== {asset['id']} =="); sys.stdout.flush()
    t0 = time.time()
    print(f"  ref image ({ref_mode}/{kind})…"); sys.stdout.flush()
    image_bytes = _ref_image(asset["prompt"], mode=ref_mode, kind=kind)
    ref_path = RUNTIME / asset["id"] / "ref.png"
    ref_path.parent.mkdir(parents=True, exist_ok=True)
    ref_path.write_bytes(image_bytes)

    print("  hunyuan mesh…"); sys.stdout.flush()
    glb = hunyuan_client.generate_mesh(image_bytes, with_texture=with_texture, timeout=3600.0)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(glb)
    shutil.copy2(out, RUNTIME / asset["id"] / "model.glb")
    meta = {
        "id": asset["id"],
        "kind": kind,
        "file": asset["file"],
        "prompt": asset["prompt"],
        "bytes": len(glb),
        "seconds": round(time.time() - t0, 1),
        "with_texture": with_texture,
        "ref_mode": ref_mode,
        "engine": "hunyuan3d",
        "path": str(out.relative_to(ROOT)),
    }
    (RUNTIME / asset["id"] / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ok {out} ({len(glb)} bytes, {meta['seconds']}s)"); sys.stdout.flush()
    return {"id": asset["id"], "status": "done", **meta}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="comma ids")
    ap.add_argument("--priority", action="store_true", help="priority=1 only")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--texture", action="store_true")
    ap.add_argument("--ref", choices=("lite", "dit"), default="lite",
                    help="reference image backend (mesh always Hunyuan3D)")
    args = ap.parse_args()

    want = {x.strip() for x in args.only.split(",") if x.strip()}
    assets = ASSETS
    if want:
        assets = [a for a in ASSETS if a["id"] in want]
    elif args.priority:
        assets = [a for a in ASSETS if a.get("priority", 9) == 1]

    print(f"plan {len(assets)} assets → hy3d (ref={args.ref})"); sys.stdout.flush()
    print(f"settings texture={get_settings().hunyuan3d_texture} url={get_settings().hunyuan3d_url}"); sys.stdout.flush()
    write_ready_json()
    manifest = load_manifest()
    for asset in assets:
        try:
            result = generate_one(
                asset, with_texture=args.texture, force=args.force, ref_mode=args.ref,
            )
        except Exception as exc:
            print(f"FAIL {asset['id']}: {exc}"); sys.stdout.flush()
            manifest.setdefault("assets", {})[asset["id"]] = {
                "status": "failed", "error": str(exc),
            }
            save_manifest(manifest)
            continue
        manifest.setdefault("assets", {})[asset["id"]] = result
        save_manifest(manifest)

    done = sum(1 for v in manifest.get("assets", {}).values() if v.get("status") in ("done", "skip"))
    print(f"manifest {MANIFEST} done/skip={done}/{len(ASSETS)}"); sys.stdout.flush()


if __name__ == "__main__":
    main()
