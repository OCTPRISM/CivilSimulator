"""Persist lab workspace snapshots to disk (v1.4 GA workspace persistence)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TYPE_CHECKING

from ..config import get_settings

if TYPE_CHECKING:
    from .workspace import LabWorkspace


def _store_dir() -> Path:
    d = Path(get_settings().data_dir) / "lab_workspaces"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _file_path(user_id: str, lab_key: str, civilization_key: str) -> Path:
    safe = f"{user_id}__{lab_key}__{civilization_key}".replace("/", "_")
    return _store_dir() / f"{safe}.json"


def load_lab_record(
    user_id: str, lab_key: str, civilization_key: str,
) -> dict[str, Any] | None:
    path = _file_path(user_id, lab_key, civilization_key)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def save_lab_snapshot(ws: "LabWorkspace", snap: dict[str, Any]) -> None:
    record = {
        "id": ws.id,
        "user_id": ws.user_id,
        "lab_key": ws.lab_key,
        "civilization_key": ws.civilization_key,
        "timeline_events": snap.get("timeline_events") or [],
        "last_report": snap.get("last_report"),
        "snapshot": snap,
    }
    path = _file_path(ws.user_id, ws.lab_key, ws.civilization_key)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=0), encoding="utf-8")
