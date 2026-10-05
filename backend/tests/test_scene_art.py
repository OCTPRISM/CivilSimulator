"""Tests for M3 Pillow scene-art plates."""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QDRANT_ENABLED", "false")
os.environ.setdefault("LLM_PROVIDER", "mock")


def test_generate_scene_plate_caches(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from app.config import get_settings
    get_settings.cache_clear()

    from app.layer1_foundation.scene_art import generate_scene_plate, scene_art_dir

    # Point cache into tmp via data_dir
    assert str(get_settings().data_dir) == str(tmp_path) or Path(get_settings().data_dir).name

    p1 = generate_scene_plate(
        genre="ancient",
        location_name="西市",
        summary="暮色酒肆",
        hour=18.0,
        tension=0.4,
        width=320,
        height=180,
    )
    assert p1.exists()
    assert p1.suffix == ".png"
    assert p1.stat().st_size > 500

    p2 = generate_scene_plate(
        genre="ancient",
        location_name="西市",
        summary="暮色酒肆",
        hour=18.0,
        tension=0.4,
        width=320,
        height=180,
    )
    assert p1 == p2

    # Different tension → different cache key
    p3 = generate_scene_plate(
        genre="ancient",
        location_name="西市",
        summary="暮色酒肆",
        hour=18.0,
        tension=0.9,
        width=320,
        height=180,
    )
    assert p3 != p1
    assert p3.exists()

    # Cache lives under data_dir/scene_art
    assert scene_art_dir().exists()


def test_api_scene_art_and_tts_info(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from app.config import get_settings
    get_settings.cache_clear()

    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    info = client.get("/api/tts/info")
    assert info.status_code == 200
    body = info.json()
    assert body.get("use_browser_speech_synthesis") is True
    assert body.get("scene_art") == "pillow_atmosphere"

    r = client.get(
        "/api/media/scene-art",
        params={
            "genre": "wuxia",
            "location": "竹林",
            "summary": "月下对峙",
            "hour": 22,
            "tension": 0.7,
        },
    )
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("image/png")
    assert len(r.content) > 500
