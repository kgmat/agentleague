"""FastAPI application entrypoint.

Wires the three layers together:
  * REST + WebSocket API (this module's routers)         — the UI-facing surface
  * the LangGraph runtime + Telegram channel              — agent execution
  * SQLAlchemy persistence                                — initialised on startup

The lifespan handler creates tables and starts the Telegram bot (if configured),
so ``docker compose up`` / ``uvicorn app.main:app`` is the single thing to run.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.channels.slack import start_slack, stop_slack
from app.channels.telegram import start_telegram, stop_telegram
from app.core.config import settings
from app.core.database import init_db
from app.core.logging import configure_logging, get_logger

logger = get_logger(__name__)


async def _load_runtime_settings() -> None:
    """Apply any persisted runtime settings (e.g. Ollama URL) on startup."""
    from app.core.database import SessionLocal
    from app.services import settings_service

    async with SessionLocal() as session:
        await settings_service.load_into_runtime(session)


async def _fail_orphaned_runs() -> None:
    """Clean up runs interrupted by a previous process exit."""
    from app.services import run_service

    await run_service.fail_orphaned_runs()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger.info("Starting %s v%s (env=%s)", settings.APP_NAME, __version__, settings.ENV)
    await init_db()
    await _load_runtime_settings()
    await _fail_orphaned_runs()
    await start_telegram()
    await start_slack()
    try:
        yield
    finally:
        await stop_telegram()
        await stop_slack()
        logger.info("Shutdown complete.")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=__version__,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Import here to avoid circulars during module import.
    from app.api import (
        routes_agents,
        routes_channels,
        routes_meta,
        routes_monitor,
        routes_runs,
        routes_settings,
        routes_templates,
        routes_workflows,
    )

    for module in (
        routes_meta,
        routes_agents,
        routes_workflows,
        routes_runs,
        routes_templates,
        routes_channels,
        routes_settings,
        routes_monitor,
    ):
        app.include_router(module.router)

    return app


app = create_app()
