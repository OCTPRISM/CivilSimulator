"""Global configuration loaded from env."""
from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

# Must match Settings.auth_secret default — R0-3 blocks this outside development.
DEFAULT_AUTH_SECRET = "civsim-dev-auth-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Runtime environment: development | test | production (also reads ENV).
    env: str = "development"

    # LLM
    llm_provider: str = "ollama"        # continuous simulation requires Ollama
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    # Ollama (M1 local inference)
    ollama_base_url: str = "http://localhost:11434"
    # Prefer qwen3.8; fall back to gpt-oss when the tagged model is missing.
    ollama_text_model: str = "qwen3.8:27b"
    ollama_text_fallbacks: str = "gpt-oss:20b,qwen3.6:35b-a3b"
    ollama_vision_model: str = "qwen3-vl:30b"
    ollama_embed_model: str = "nomic-embed-text"

    # Persistence
    data_dir: str = "data/runtime"
    sqlite_path: str = "data/runtime/civsim.db"

    # Qdrant vector memory (M1)
    # Default: embedded local store under data_dir (no Docker required).
    # Set QDRANT_URL=http://localhost:6333 to use a Qdrant server instead.
    qdrant_enabled: bool = True
    qdrant_url: str | None = None
    qdrant_path: str = "data/runtime/qdrant"
    qdrant_collection: str = "civsim_memories"
    qdrant_api_key: str | None = None

    # Narrative
    max_agents_per_scene: int = 4
    tick_seconds: float = 2.0

    # Dormancy / background world
    # Real-time seconds between background world ticks while any player is dormant.
    background_tick_seconds: float = 5.0
    # One atomic Ollama inference per active world. The next tick starts only
    # after the previous inference completes, so slow local models never pile up.
    live_simulation_tick_seconds: float = 15.0
    # Deterministic market clears on a faster cadence for validation UX.
    finance_tick_seconds: float = 3.0
    # No heartbeat for this many seconds → auto-dormant.
    presence_timeout_seconds: float = 45.0
    # Max world_events returned in a wake briefing.
    wake_briefing_max_events: int = 24

    # Reflection / tension
    reflection_every_ticks: int = 5
    tension_low_threshold: float = 0.35

    # Optional Redis room bus (v0.4 MP-4). Unset = single-process fan-out.
    # If set but unreachable, process still starts in single-process mode.
    redis_url: str | None = None

    # Auth
    auth_secret: str = DEFAULT_AUTH_SECRET

    # CORS — comma-separated origins (R0-4). Default covers local Next.js ports.
    cors_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:3001,http://localhost:3002,http://localhost:3003"
    )

    # Rate limits (R0-5) — per client IP, sliding 60s window.
    rate_limit_enabled: bool = True
    rate_limit_register_per_minute: int = 5
    rate_limit_play_per_minute: int = 60
    # Only trust X-Forwarded-For when sitting behind a known reverse proxy.
    trust_proxy_headers: bool = False

    # Invite / password (R1-5)
    invite_only: bool = False
    invite_code: str = ""
    min_password_length: int = 8

    # Hunyuan3D-2 (local image → 3D)
    hunyuan3d_enabled: bool = True
    hunyuan3d_url: str = "http://127.0.0.1:8080"
    hunyuan3d_model: str = "tencent/Hunyuan3D-2mini"
    hunyuan3d_subfolder: str = "hunyuan3d-dit-v2-mini-turbo"
    hunyuan3d_texture: bool = False  # Mac: shape-only unless CUDA rasterizer built
    hunyuan3d_device: str = "cpu"  # macOS 26: MPS broken; use cpu
    hunyuan3d_text2img_mode: str = "dit"  # lite (fast) | dit (HunyuanDiT)
    generator_output_dir: str = "data/runtime/generator"


def parse_cors_origins(raw: str | None) -> list[str]:
    """Split CORS_ORIGINS env into a list; empty → localhost defaults for dev."""
    text = (raw or "").strip()
    if not text:
        return [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    if text == "*":
        return ["*"]
    return [part.strip() for part in text.split(",") if part.strip()]


def assert_auth_secret_safe(settings: Settings | None = None) -> None:
    """R0-3: refuse default AUTH_SECRET outside local development."""
    s = settings or get_settings()
    env = (s.env or "development").strip().lower()
    # Only interactive local envs may use the baked-in secret.
    # ENV=test / staging / production must set AUTH_SECRET explicitly.
    if env in ("development", "dev"):
        return
    secret = (s.auth_secret or "").strip()
    if not secret or secret == DEFAULT_AUTH_SECRET:
        raise RuntimeError(
            "拒绝启动：非开发环境必须设置自定义 AUTH_SECRET"
            f"（当前 ENV={s.env!r} 仍使用默认密钥）。"
            "请在环境变量中设置 AUTH_SECRET=… 后再启动。"
        )


def assert_cors_safe(settings: Settings | None = None) -> None:
    """R0-4: production must not use wildcard CORS."""
    s = settings or get_settings()
    if not is_production_env(s):
        return
    origins = parse_cors_origins(s.cors_origins)
    if origins == ["*"]:
        raise RuntimeError(
            "拒绝启动：生产环境禁止 CORS_ORIGINS=*。"
            "请改为明确的前端源列表，例如 https://preview.example.com"
        )


def is_production_env(settings: Settings | None = None) -> bool:
    s = settings or get_settings()
    return (s.env or "development").strip().lower() in ("production", "prod")


def effective_invite_only(settings: Settings | None = None) -> bool:
    """R1-5: production always requires invite codes; otherwise honor INVITE_ONLY."""
    s = settings or get_settings()
    if is_production_env(s):
        return True
    return bool(s.invite_only)


def assert_invite_config_safe(settings: Settings | None = None) -> None:
    """R1-5: production must configure a non-empty INVITE_CODE."""
    s = settings or get_settings()
    if not is_production_env(s):
        return
    if not (s.invite_code or "").strip():
        raise RuntimeError(
            "拒绝启动：生产环境必须设置 INVITE_CODE（邀测注册，R1-5）。"
            f"当前 ENV={s.env!r}。"
        )


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    # Auto-enable openai if key provided
    if s.openai_api_key and s.llm_provider == "mock":
        s.llm_provider = "openai"
    return s
