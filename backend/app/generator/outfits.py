"""Per-civilization character outfit packs — loaded from civilization_outfits.json.

Source of truth for playable roles: backend/app/seeds/player_catalog.json
Regenerate JSON + assets:
  python3 backend/scripts/sync_role_assets_from_catalog.py
  (then re-run the JSON emitter if needed — sync writes catalogs; JSON is
   regenerated alongside or via the helper in that script's follow-up.)
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_DATA_PATH = Path(__file__).with_name("civilization_outfits.json")


@lru_cache(maxsize=1)
def _data() -> dict[str, Any]:
    if not _DATA_PATH.is_file():
        return {
            "civ_meta": {},
            "default_role": {},
            "mesh_genre": {},
            "outfits": {},
        }
    return json.loads(_DATA_PATH.read_text(encoding="utf-8"))


def _civ_meta() -> dict[str, dict[str, str]]:
    return _data().get("civ_meta") or {}


def _outfits_map() -> dict[str, list[dict[str, Any]]]:
    return _data().get("outfits") or {}


# Module-level snapshots refreshed on import (scripts may import these names)
CIV_META: dict[str, dict[str, str]] = {}
MESH_GENRE: dict[str, str] = {}
DEFAULT_ROLE: dict[str, str] = {}
CIVILIZATION_OUTFITS: dict[str, list[dict[str, Any]]] = {}
OUTFITS: list[dict[str, Any]] = []


def _refresh_module_aliases() -> None:
    global CIV_META, MESH_GENRE, DEFAULT_ROLE, CIVILIZATION_OUTFITS, OUTFITS
    d = _data()
    CIV_META = dict(d.get("civ_meta") or {})
    MESH_GENRE = dict(d.get("mesh_genre") or {})
    DEFAULT_ROLE = dict(d.get("default_role") or {})
    CIVILIZATION_OUTFITS = {k: [dict(o) for o in v] for k, v in (d.get("outfits") or {}).items()}
    OUTFITS = list_outfits(next(iter(CIVILIZATION_OUTFITS), None))


def list_civilizations() -> list[dict[str, Any]]:
    out = []
    for key, meta in CIV_META.items():
        outfits = CIVILIZATION_OUTFITS.get(key, [])
        out.append({
            "id": key,
            "name": meta.get("name", key),
            "genre": meta.get("genre", key),
            "era": meta.get("era", ""),
            "outfit_count": len(outfits),
            "default_role": DEFAULT_ROLE.get(key),
            "character_url": f"/models/characters/civilizations/{key}/character/body.glb",
            "catalog_url": f"/models/characters/civilizations/{key}/catalog.json",
        })
    return out


def list_outfits(civilization: str | None = None) -> list[dict[str, Any]]:
    if civilization:
        civ = civilization.strip().lower()
        packs = CIVILIZATION_OUTFITS.get(civ, [])
        meta = CIV_META.get(civ, {})
        return [_enrich(civ, meta, o) for o in packs]
    flat: list[dict[str, Any]] = []
    for civ, packs in CIVILIZATION_OUTFITS.items():
        meta = CIV_META.get(civ, {})
        for o in packs:
            flat.append(_enrich(civ, meta, o))
    return flat


def _enrich(civ: str, meta: dict[str, str], outfit: dict[str, Any]) -> dict[str, Any]:
    oid = outfit["id"]
    return {
        **outfit,
        "civilization": civ,
        "era": meta.get("era", outfit.get("era", "")),
        "civilization_name": meta.get("name", civ),
        "asset_dir": f"/models/characters/civilizations/{civ}/outfits/{oid}",
        "meta_url": f"/models/characters/civilizations/{civ}/outfits/{oid}/meta.json",
        "body_url": f"/models/characters/roles/{oid}/body.glb",
        "props_urls": [
            f"/models/characters/civilizations/{civ}/props/{_slug(p)}/prop.glb"
            for p in outfit.get("props", [])
        ],
    }


def _slug(name: str) -> str:
    s = "".join(ch if ch.isalnum() else "_" for ch in name.strip())
    while "__" in s:
        s = s.replace("__", "_")
    return s.strip("_").lower() or "prop"


def get_outfit(outfit_id: str | None, civilization: str | None = None) -> dict[str, Any] | None:
    if not outfit_id:
        return None
    if civilization:
        for o in list_outfits(civilization):
            if o["id"] == outfit_id:
                return o
        return None
    for o in list_outfits(None):
        if o["id"] == outfit_id:
            return o
    return None


def apply_outfit_to_prompt(
    prompt: str,
    outfit_id: str | None,
    *,
    civilization: str | None = None,
) -> tuple[str, dict[str, Any] | None]:
    outfit = get_outfit(outfit_id, civilization)
    base = (prompt or "").strip()
    if not outfit:
        return base, None
    merged = f"{base},{outfit['prompt']}" if base else outfit["prompt"]
    return merged, outfit


_refresh_module_aliases()
OUTFITS = list_outfits(next(iter(CIVILIZATION_OUTFITS), None)) if CIVILIZATION_OUTFITS else []
