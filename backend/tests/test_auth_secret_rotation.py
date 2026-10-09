"""v0.5 P-6: AUTH_SECRET_PREVIOUS rotation grace."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QDRANT_ENABLED", "false")
os.environ.setdefault("LLM_PROVIDER", "mock")

from app.config import DEFAULT_AUTH_SECRET, Settings, assert_auth_secret_safe, get_settings


def _isolate(tmp_path, monkeypatch):
    db = tmp_path / "civsim.db"
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SQLITE_PATH", str(db))
    get_settings.cache_clear()
    import app.layer6_persistence.sqlite_db as sqlite_db
    import app.layer6_persistence.users as users
    import app.layer6_persistence.event_store as event_store
    if sqlite_db._CONN is not None:
        try:
            sqlite_db._CONN.close()
        except Exception:
            pass
        sqlite_db._CONN = None
    users._SCHEMA_READY = False
    event_store._SCHEMA_READY = False


def test_previous_equals_current_blocked_outside_dev():
    with pytest.raises(RuntimeError, match="AUTH_SECRET_PREVIOUS"):
        assert_auth_secret_safe(
            Settings(
                env="production",
                auth_secret="prod-secret-a-long-enough",
                auth_secret_previous="prod-secret-a-long-enough",
            )
        )


def test_previous_default_blocked_outside_dev():
    with pytest.raises(RuntimeError, match="AUTH_SECRET_PREVIOUS"):
        assert_auth_secret_safe(
            Settings(
                env="production",
                auth_secret="prod-secret-a-long-enough",
                auth_secret_previous=DEFAULT_AUTH_SECRET,
            )
        )


def test_verify_accepts_token_signed_with_previous(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("AUTH_SECRET", "old-secret-for-rotation-tests-32")
    monkeypatch.delenv("AUTH_SECRET_PREVIOUS", raising=False)
    get_settings.cache_clear()

    from app.layer6_persistence import users as users_mod

    user = users_mod.create_user("rotuser", "password12345", "Rot")
    old_token = users_mod.make_token(user.id)

    monkeypatch.setenv("AUTH_SECRET", "new-secret-for-rotation-tests-32")
    monkeypatch.setenv("AUTH_SECRET_PREVIOUS", "old-secret-for-rotation-tests-32")
    get_settings.cache_clear()

    assert users_mod.verify_token(old_token) == user.id

    new_token = users_mod.make_token(user.id)
    assert users_mod.verify_token(new_token) == user.id

    monkeypatch.delenv("AUTH_SECRET_PREVIOUS", raising=False)
    get_settings.cache_clear()
    assert users_mod.verify_token(old_token) is None
    assert users_mod.verify_token(new_token) == user.id

    get_settings.cache_clear()
