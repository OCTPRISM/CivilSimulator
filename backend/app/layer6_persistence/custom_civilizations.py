"""User-authored custom civilizations — SQLite backed."""
from __future__ import annotations

import json
import time
from typing import Any
from uuid import uuid4

from .sqlite_db import db_lock, exec_script, get_conn

_SCHEMA_READY = False

DEFAULT_CLASS_STRUCTURE = {
    "ruling": 0.05,
    "middle": 0.35,
    "labor": 0.50,
    "marginal": 0.10,
}

DEFAULT_AGE_STRUCTURE = {
    "child": 0.18,
    "youth": 0.22,
    "adult": 0.40,
    "middle_aged": 0.12,
    "elder": 0.08,
}


def _ensure_schema() -> None:
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    exec_script("""
    CREATE TABLE IF NOT EXISTS custom_civilizations (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        name TEXT NOT NULL,
        config_json TEXT NOT NULL,
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_custom_civ_user
              ON custom_civilizations(user_id, updated_at DESC);
    """)
    _SCHEMA_READY = True


def _normalize_ratios(d: dict[str, float]) -> dict[str, float]:
    total = sum(max(0.0, float(v)) for v in d.values())
    if total <= 1e-9:
        return dict(DEFAULT_CLASS_STRUCTURE)
    return {k: max(0.0, float(v)) / total for k, v in d.items()}


def validate_custom_config(config: dict[str, Any]) -> dict[str, Any]:
    logic = (config.get("operating_logic") or "").strip()
    if not logic:
        raise ValueError("文明运行逻辑为必填项")
    name = (config.get("name") or "未命名文明").strip()[:80]
    out = {
        "name": name,
        "class_structure": _normalize_ratios(config.get("class_structure") or DEFAULT_CLASS_STRUCTURE),
        "age_structure": _normalize_ratios(config.get("age_structure") or DEFAULT_AGE_STRUCTURE),
        "operating_logic": logic[:4000],
        "government_form": (config.get("government_form") or "未指定").strip()[:500],
        "professions": list(config.get("professions") or []),
        "roles": list(config.get("roles") or []),
        "historical_events": list(config.get("historical_events") or []),
        "current_stage": (config.get("current_stage") or "起始阶段").strip()[:500],
    }
    return out


def create_custom_civilization(user_id: str, config: dict[str, Any]) -> dict[str, Any]:
    _ensure_schema()
    cfg = validate_custom_config(config)
    cid = uuid4().hex[:12]
    now = time.time()
    key = f"custom_{cid}"
    row = {
        "id": cid,
        "user_id": user_id,
        "key": key,
        "name": cfg["name"],
        "config": cfg,
        "created_at": now,
        "updated_at": now,
    }
    with db_lock():
        get_conn().execute(
            "INSERT INTO custom_civilizations (id, user_id, name, config_json, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (cid, user_id, cfg["name"], json.dumps(cfg, ensure_ascii=False), now, now),
        )
        get_conn().commit()
    return row


def get_custom_civilization(civ_id: str, user_id: str | None = None) -> dict[str, Any] | None:
    _ensure_schema()
    with db_lock():
        if user_id:
            cur = get_conn().execute(
                "SELECT id, user_id, name, config_json, created_at, updated_at"
                " FROM custom_civilizations WHERE id = ? AND user_id = ?",
                (civ_id, user_id),
            )
        else:
            cur = get_conn().execute(
                "SELECT id, user_id, name, config_json, created_at, updated_at"
                " FROM custom_civilizations WHERE id = ?",
                (civ_id,),
            )
        row = cur.fetchone()
    if not row:
        return None
    cfg = json.loads(row[3])
    return {
        "id": row[0],
        "user_id": row[1],
        "key": f"custom_{row[0]}",
        "name": row[2],
        "config": cfg,
        "created_at": row[4],
        "updated_at": row[5],
    }


def get_custom_by_key(key: str, user_id: str | None = None) -> dict[str, Any] | None:
    if not key.startswith("custom_"):
        return None
    cid = key[len("custom_"):]
    return get_custom_civilization(cid, user_id=user_id)


def list_custom_civilizations(user_id: str) -> list[dict[str, Any]]:
    _ensure_schema()
    with db_lock():
        cur = get_conn().execute(
            "SELECT id, name, config_json, created_at, updated_at"
            " FROM custom_civilizations WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        )
        rows = cur.fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        cfg = json.loads(row[2])
        out.append({
            "id": row[0],
            "key": f"custom_{row[0]}",
            "name": row[1],
            "genre": "custom",
            "premise": cfg.get("current_stage") or cfg.get("operating_logic", "")[:120],
            "is_custom": True,
            "created_at": row[3],
            "updated_at": row[4],
        })
    return out


def delete_custom_civilization(civ_id: str, user_id: str) -> bool:
    _ensure_schema()
    with db_lock():
        cur = get_conn().execute(
            "DELETE FROM custom_civilizations WHERE id = ? AND user_id = ?",
            (civ_id, user_id),
        )
        get_conn().commit()
        return cur.rowcount > 0
