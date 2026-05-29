"""Metadata endpoints: available tools, providers, health, settings."""
from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.runtime.providers import list_providers
from app.runtime.tools import list_tools

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.ENV}


@router.get("/tools")
async def get_tools():
    return list_tools()


@router.get("/providers")
async def get_providers():
    return list_providers()


@router.get("/config")
async def get_config():
    """Non-secret runtime config the UI uses to adapt itself."""
    return {
        "default_provider": settings.DEFAULT_PROVIDER,
        "default_model": settings.DEFAULT_MODEL,
        "telegram_enabled": bool(settings.TELEGRAM_BOT_TOKEN) and settings.ENABLE_TELEGRAM,
        "max_workflow_steps": settings.MAX_WORKFLOW_STEPS,
    }
