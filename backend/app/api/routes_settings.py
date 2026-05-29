"""Runtime settings + live Ollama model discovery."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.runtime.providers import fetch_ollama_models, fetch_provider_models
from app.services import settings_service

router = APIRouter(prefix="/api/settings", tags=["settings"])


class OllamaUrlIn(BaseModel):
    base_url: str


class DefaultModelIn(BaseModel):
    model: str


@router.get("")
async def get_settings(session: AsyncSession = Depends(get_session)):
    return await settings_service.get_effective_config(session)


@router.put("/ollama")
async def update_ollama_url(data: OllamaUrlIn, session: AsyncSession = Depends(get_session)):
    """Save the Ollama server URL and return whether it's reachable + its models."""
    return await settings_service.set_ollama_base_url(session, data.base_url)


@router.put("/default-model")
async def update_default_model(data: DefaultModelIn, session: AsyncSession = Depends(get_session)):
    await settings_service.set_default_model(session, data.model)
    return {"default_model": data.model}


@router.get("/ollama/models")
async def list_ollama_models(base_url: str | None = Query(default=None)):
    """Fetch the live installed-model list from the (given or active) Ollama server."""
    return await fetch_ollama_models(base_url)


@router.get("/models")
async def list_models(
    provider: str = Query(default="ollama"),
    base_url: str | None = Query(default=None),
):
    """Live model discovery for any provider (ollama tags / OpenAI-compatible /models)."""
    return await fetch_provider_models(provider, base_url)
