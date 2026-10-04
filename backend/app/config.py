"""Global configuration loaded from env."""
from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM
    llm_provider: str = "ollama"        # continuous simulation requires Ollama
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_text_model: str = "qwen3.6:35b-a3b"
    ollama_vision_model: str = "qwen3-vl:30b"
    ollama_embed_model: str = "nomic-embed-text"

    # Persistence
    data_dir: str = "data/runtime"
    sqlite_path: str = "data/runtime/civsim.db"

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

    # Multiplayer
    redis_url: str | None = None        # if set, sessions go to Redis

    # Auth
    auth_secret: str = "civsim-dev-auth-secret-change-me"

    # Hunyuan3D-2 (local image → 3D)
    hunyuan3d_enabled: bool = True
    hunyuan3d_url: str = "http://127.0.0.1:8080"
    hunyuan3d_model: str = "tencent/Hunyuan3D-2mini"
    hunyuan3d_subfolder: str = "hunyuan3d-dit-v2-mini-turbo"
    hunyuan3d_texture: bool = False  # Mac: shape-only unless CUDA rasterizer built
    hunyuan3d_device: str = "cpu"  # macOS 26: MPS broken; use cpu
    hunyuan3d_text2img_mode: str = "dit"  # lite (fast) | dit (HunyuanDiT)
    generator_output_dir: str = "data/runtime/generator"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    # Auto-enable openai if key provided
    if s.openai_api_key and s.llm_provider == "mock":
        s.llm_provider = "openai"
    return s
