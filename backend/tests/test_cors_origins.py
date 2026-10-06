"""R0-4: CORS origins come from CORS_ORIGINS env (not open *)."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.config import parse_cors_origins


def test_parse_cors_origins_list():
    assert parse_cors_origins("https://a.example, https://b.example") == [
        "https://a.example",
        "https://b.example",
    ]
    assert parse_cors_origins("*") == ["*"]
    assert "http://localhost:3000" in parse_cors_origins("")


def test_cors_allows_configured_origin_only():
    origins = parse_cors_origins(
        "http://localhost:3000,https://play.example.com",
    )
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    client = TestClient(app)
    allowed = client.options(
        "/ping",
        headers={
            "Origin": "https://play.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert allowed.headers.get("access-control-allow-origin") == "https://play.example.com"

    denied = client.options(
        "/ping",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert denied.headers.get("access-control-allow-origin") != "https://evil.example"


def test_main_module_uses_parsed_cors():
    """Smoke: main wires CORS from settings (defaults include localhost)."""
    from app import main as main_mod
    from app.config import get_settings

    origins = parse_cors_origins(get_settings().cors_origins)
    assert origins == main_mod._CORS_ORIGINS
    assert "*" not in origins or origins == ["*"]
    # Default install should not be wide-open * unless explicitly configured.
    assert main_mod._CORS_ORIGINS != ["*"] or get_settings().cors_origins.strip() == "*"
