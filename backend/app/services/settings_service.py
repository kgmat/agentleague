"""Runtime-tunable settings, persisted in the ``settings`` table.

Currently exposes the Ollama base URL (and default model) so they can be changed
live from the UI and survive restarts. On startup, ``load_into_runtime`` pushes
any saved Ollama URL into the provider layer.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models import Setting
from app.runtime import providers

logger = get_logger(__name__)

OLLAMA_URL_KEY = "ollama_base_url"
DEFAULT_MODEL_KEY = "default_model"


async def get_setting(session: AsyncSession, key: str, default: str | None = None) -> str | None:
    row = await session.get(Setting, key)
    return row.value if row else default


async def set_setting(session: AsyncSession, key: str, value: str) -> None:
    row = await session.get(Setting, key)
    if row:
        row.value = value
    else:
        session.add(Setting(key=key, value=value))
    await session.flush()


async def get_effective_config(session: AsyncSession) -> dict:
    return {
        "ollama_base_url": await get_setting(session, OLLAMA_URL_KEY, settings.OLLAMA_BASE_URL),
        "default_model": await get_setting(session, DEFAULT_MODEL_KEY, settings.DEFAULT_MODEL),
    }


async def set_ollama_base_url(session: AsyncSession, base_url: str) -> dict:
    """Persist the Ollama URL, push it into the runtime, and probe it for models."""
    clean = base_url.rstrip("/")
    await set_setting(session, OLLAMA_URL_KEY, clean)
    providers.set_ollama_base_url(clean)
    return await providers.fetch_ollama_models(clean)


async def set_default_model(session: AsyncSession, model: str) -> None:
    await set_setting(session, DEFAULT_MODEL_KEY, model)


async def load_into_runtime(session: AsyncSession) -> None:
    """Called on startup: apply any persisted Ollama URL to the provider layer."""
    saved = await get_setting(session, OLLAMA_URL_KEY)
    if saved:
        providers.set_ollama_base_url(saved)
        logger.info("Loaded Ollama base URL from settings: %s", saved)
