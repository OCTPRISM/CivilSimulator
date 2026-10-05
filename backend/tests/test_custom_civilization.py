"""Tests for M4 custom civilization seed + rule editor."""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QDRANT_ENABLED", "false")
os.environ.setdefault("LLM_PROVIDER", "mock")


def _isolate_db(tmp_path, monkeypatch):
    db = tmp_path / "civsim.db"
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SQLITE_PATH", str(db))
    from app.config import get_settings
    get_settings.cache_clear()
    import app.layer6_persistence.sqlite_db as sqlite_db
    import app.layer6_persistence.custom_civilizations as cc
    import app.layer6_persistence.users as users
    if sqlite_db._CONN is not None:
        try:
            sqlite_db._CONN.close()
        except Exception:
            pass
        sqlite_db._CONN = None
    cc._SCHEMA_READY = False
    users._SCHEMA_READY = False
    return db


def test_validate_and_materialize_custom_seed(tmp_path, monkeypatch):
    _isolate_db(tmp_path, monkeypatch)

    from app.layer6_persistence.custom_civilizations import (
        create_custom_civilization,
        update_custom_civilization,
        delete_custom_civilization,
        validate_custom_config,
    )
    from app.layer2_civilization.civilization_resolver import custom_to_seed

    cfg = validate_custom_config({
        "name": "盐铁联邦",
        "genre": "ancient",
        "premise": "盐课改制前夜，沿海商帮与朝廷对峙。",
        "operating_logic": "盐铁专营为财政命脉，走私即叛乱。",
        "government_form": "盐运使节制",
        "current_stage": "改制前夜",
        "rules": ["无超自然力量", "盐课即国命"],
        "locations": [
            {"name": "通州盐场", "description": "熬波煮海。", "tags": ["盐场", "苦役"]},
            {"name": "扬州钞关", "description": "商船过关查验。", "tags": ["关税"]},
        ],
        "factions": [
            {"name": "盐运司", "ideology": "专营护税"},
            {"name": "海商帮", "ideology": "走私求存"},
        ],
        "opening_scene": "潮退之后，你看见盐田反光。",
        "professions": [{"name": "盐丁", "description": "煮盐苦力", "playable": True}],
        "roles": [{"name": "私盐客", "persona": "走夜路的人", "profession": "走私"}],
        "historical_events": [{"era": "永和", "title": "盐课骤增", "description": "民变初起"}],
        "class_structure": {"ruling": 0.1, "middle": 0.3, "labor": 0.5, "marginal": 0.1},
    })
    assert cfg["genre"] == "ancient"
    assert len(cfg["rules"]) == 2
    assert cfg["locations"][0]["name"] == "通州盐场"

    row = create_custom_civilization("user_test_m4", dict(cfg))
    assert row["key"].startswith("custom_")
    seed = custom_to_seed(row)
    assert seed.name == "盐铁联邦"
    assert seed.genre == "ancient"
    assert "盐课即国命" in seed.rules
    assert any(loc["name"] == "通州盐场" for loc in seed.locations)
    assert any(fac["name"] == "海商帮" for fac in seed.factions)
    assert "潮退" in seed.opening_scene
    world = seed.materialize()
    assert len(world.locations) >= 2

    updated = update_custom_civilization(row["id"], "user_test_m4", {
        **cfg,
        "name": "盐铁联邦·改",
        "rules": ["无超自然力量", "盐课即国命", "夜禁森严"],
    })
    assert updated is not None
    assert updated["name"] == "盐铁联邦·改"
    seed2 = custom_to_seed(updated)
    assert len(seed2.rules) == 3

    assert delete_custom_civilization(row["id"], "user_test_m4") is True
    assert delete_custom_civilization(row["id"], "user_test_m4") is False


def test_api_custom_civilization_crud(tmp_path, monkeypatch):
    _isolate_db(tmp_path, monkeypatch)

    from fastapi.testclient import TestClient
    from app.main import app
    from app.session import _SESSIONS

    _SESSIONS.clear()
    client = TestClient(app)
    uname = f"m4_api_{Path(tmp_path).name[-6:]}"
    reg = client.post("/api/auth/register", json={
        "username": uname, "password": "m4-pass-12345", "display_name": "M4",
    })
    assert reg.status_code == 200, reg.text
    token = reg.json()["token"]
    h = {"Authorization": f"Bearer {token}"}

    body = {
        "name": "星港公社",
        "genre": "scifi",
        "premise": "轨道城邦资源配给改革。",
        "operating_logic": "氧气配额决定身份。",
        "rules": ["真空外禁止肉身出行"],
        "locations": [{"name": "港环A", "description": "停泊区", "tags": ["港口"]}],
        "factions": [{"name": "港务会", "ideology": "配额公正"}],
        "opening_scene": "气闸嘶鸣。",
        "current_stage": "配给危机",
        "government_form": "港务委员会",
        "roles": [{"name": "气闸工", "persona": "守门人", "profession": "工人"}],
    }
    created = client.post("/api/civilizations/custom", json=body, headers=h)
    assert created.status_code == 200, created.text
    civ = created.json()["civilization"]
    assert civ["is_custom"] is True
    assert civ["genre"] == "scifi"
    civ_id = civ["id"]
    key = civ["key"]

    listed = client.get("/api/civilizations/custom", headers=h)
    assert listed.status_code == 200
    assert any(c["id"] == civ_id for c in listed.json()["civilizations"])

    seeds = client.get("/api/seeds", headers=h)
    assert seeds.status_code == 200
    assert any(s["key"] == key for s in seeds.json()["seeds"])

    catalog = client.get(f"/api/seeds/{key}/characters", headers=h)
    assert catalog.status_code == 200
    cats = catalog.json().get("categories") or []
    assert cats and cats[0].get("variants")
    variants = cats[0]["variants"]

    body["name"] = "星港公社·改"
    body["rules"] = ["真空外禁止肉身出行", "配额可交易"]
    upd = client.put(f"/api/civilizations/custom/{civ_id}", json=body, headers=h)
    assert upd.status_code == 200, upd.text
    assert upd.json()["civilization"]["name"] == "星港公社·改"

    sess = client.post("/api/sessions", json={
        "seed_key": key,
        "category_key": cats[0]["key"],
        "variant_key": variants[0]["key"],
    }, headers=h)
    assert sess.status_code == 200, sess.text
    session = sess.json()["session"]
    world = session.get("world") or {}
    assert world.get("genre") == "scifi"
    assert any(loc.get("name") == "港环A" for loc in (world.get("locations") or []))

    deleted = client.delete(f"/api/civilizations/custom/{civ_id}", headers=h)
    assert deleted.status_code == 200
    assert deleted.json().get("ok") is True
    _SESSIONS.clear()
