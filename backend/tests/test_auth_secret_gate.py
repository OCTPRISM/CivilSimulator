"""R0-3: non-development environments must not use the default AUTH_SECRET."""
from __future__ import annotations

import pytest

from app.config import (
    DEFAULT_AUTH_SECRET,
    Settings,
    assert_auth_secret_safe,
    assert_cors_safe,
)


def test_default_secret_allowed_in_development():
    assert_auth_secret_safe(Settings(env="development", auth_secret=DEFAULT_AUTH_SECRET))
    assert_auth_secret_safe(Settings(env="dev", auth_secret=DEFAULT_AUTH_SECRET))


def test_default_secret_blocked_outside_development():
    for env in ("test", "staging", "production", "prod"):
        with pytest.raises(RuntimeError, match="AUTH_SECRET"):
            assert_auth_secret_safe(
                Settings(env=env, auth_secret=DEFAULT_AUTH_SECRET),
            )


def test_custom_secret_allowed_in_production():
    assert_auth_secret_safe(
        Settings(env="production", auth_secret="prod-secret-please-rotate-me"),
    )


def test_empty_secret_blocked_in_production():
    with pytest.raises(RuntimeError, match="AUTH_SECRET"):
        assert_auth_secret_safe(Settings(env="production", auth_secret="  "))


def test_wildcard_cors_blocked_in_production():
    with pytest.raises(RuntimeError, match="CORS"):
        assert_cors_safe(Settings(env="production", cors_origins="*"))
    assert_cors_safe(Settings(env="development", cors_origins="*"))


def test_lifespan_refuses_default_in_production(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("AUTH_SECRET", DEFAULT_AUTH_SECRET)
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("QDRANT_ENABLED", "false")
    from app.config import get_settings
    get_settings.cache_clear()

    from fastapi.testclient import TestClient
    from app.main import app

    with pytest.raises(RuntimeError, match="AUTH_SECRET"):
        with TestClient(app):
            pass

    get_settings.cache_clear()
