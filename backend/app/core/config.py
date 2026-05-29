"""Application configuration, loaded from environment variables.

A single ``settings`` object is imported across the app. All values have
sensible local-first defaults so the platform boots with zero configuration,
while remaining overridable for Docker / production.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- General ---
    APP_NAME: str = "AgentLeague"
    ENV: str = "local"
    LOG_LEVEL: str = "INFO"

    # --- Persistence ---
    # Async SQLAlchemy URL. Defaults to a local SQLite file so the backend can
    # run with no external database; Docker Compose overrides this with Postgres.
    DATABASE_URL: str = "sqlite+aiosqlite:///./orchestrator.db"

    # --- Message bus / pub-sub for live monitoring ---
    # When unset, the platform falls back to an in-process async event bus so a
    # single ``uvicorn`` process still works without Redis.
    REDIS_URL: str | None = None

    # --- LLM provider (pluggable) ---
    # The default provider. One of: "ollama", "openai", "anthropic".
    # "openai" also covers any OpenAI-compatible gateway (e.g. a hosted vLLM /
    # Ollama-OpenAI endpoint) by setting OPENAI_BASE_URL + OPENAI_API_KEY.
    DEFAULT_PROVIDER: str = "ollama"
    DEFAULT_MODEL: str = "qwen2.5"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OPENAI_API_KEY: str | None = None
    # Custom OpenAI-compatible base URL (must end in /v1). None = real OpenAI.
    OPENAI_BASE_URL: str | None = None
    OPENAI_TIMEOUT: int = 180  # reasoning models can be slow
    ANTHROPIC_API_KEY: str | None = None

    # Qwen/vLLM "thinking" (reasoning) mode. Default OFF for speed and to avoid
    # huge reasoning generations (which cause latency + Cloudflare 524s). Only
    # applied to custom OpenAI-compatible gateways, never to real OpenAI.
    ENABLE_THINKING: bool = False

    # --- Runtime guardrails ---
    MAX_WORKFLOW_STEPS: int = 40  # hard ceiling on node visits per run
    LLM_TIMEOUT_SECONDS: int = 120

    # --- Messaging channel: Telegram ---
    TELEGRAM_BOT_TOKEN: str | None = None
    # Which agent (by id) the Telegram bot routes inbound messages to. If unset,
    # the bot can also be pointed at a workflow via TELEGRAM_WORKFLOW_ID.
    TELEGRAM_AGENT_ID: str | None = None
    TELEGRAM_WORKFLOW_ID: str | None = None
    ENABLE_TELEGRAM: bool = True

    # --- Messaging channel: Slack (Socket Mode — no public webhook needed) ---
    SLACK_BOT_TOKEN: str | None = None     # xoxb-...
    SLACK_APP_TOKEN: str | None = None     # xapp-... (connections:write, for Socket Mode)
    SLACK_AGENT_ID: str | None = None
    SLACK_WORKFLOW_ID: str | None = None
    ENABLE_SLACK: bool = True

    # --- CORS (frontend dev server) ---
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
