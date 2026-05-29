"""Pluggable LLM provider layer.

The platform is provider-agnostic: an agent declares ``provider`` + ``model``
and this module returns a configured LangChain chat model. Ollama is the
local-first default; OpenAI and Anthropic are wired in and activate when their
API keys are present. Adding a provider = adding one branch in ``build_chat_model``.

Token accounting is normalised here so the rest of the system never has to care
which provider produced a response.
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx
from langchain_core.language_models.chat_models import BaseChatModel

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


# Runtime-mutable Ollama base URL. Initialised from env, but can be overridden
# at runtime from the UI (and persisted) without restarting — see
# ``set_ollama_base_url`` / settings_service.
_ollama_base_url: str = settings.OLLAMA_BASE_URL


def set_ollama_base_url(url: str | None) -> None:
    """Update the active Ollama server URL used for new model instances."""
    global _ollama_base_url
    _ollama_base_url = (url or settings.OLLAMA_BASE_URL).rstrip("/")


def get_ollama_base_url() -> str:
    return _ollama_base_url


async def fetch_ollama_models(base_url: str | None = None) -> dict:
    """Query a live Ollama server's installed models via ``GET /api/tags``.

    Returns {"available": bool, "models": [str], "base_url": str, "error": str|None}
    so the UI can both populate the model dropdown and report reachability.
    """
    url = (base_url or _ollama_base_url).rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(f"{url}/api/tags")
            resp.raise_for_status()
            data = resp.json()
        models = sorted(m["name"] for m in data.get("models", []))
        return {"available": True, "models": models, "base_url": url, "error": None}
    except Exception as exc:  # unreachable server / bad URL — report, don't raise
        logger.warning("Could not fetch Ollama models from %s: %s", url, exc)
        return {"available": False, "models": [], "base_url": url, "error": str(exc)}


async def fetch_openai_models(base_url: str | None = None) -> dict:
    """List models from an OpenAI-compatible endpoint via ``GET {base}/models``."""
    url = (base_url or settings.OPENAI_BASE_URL or "https://api.openai.com/v1").rstrip("/")
    if not settings.OPENAI_API_KEY:
        return {"available": False, "models": [], "base_url": url, "error": "OPENAI_API_KEY not set"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{url}/models", headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}
            )
            resp.raise_for_status()
            data = resp.json()
        models = sorted(m["id"] for m in data.get("data", []))
        return {"available": True, "models": models, "base_url": url, "error": None}
    except Exception as exc:
        logger.warning("Could not fetch OpenAI-compatible models from %s: %s", url, exc)
        return {"available": False, "models": [], "base_url": url, "error": str(exc)}


async def fetch_provider_models(provider: str, base_url: str | None = None) -> dict:
    """Live model discovery for a given provider (used by the agent editor)."""
    provider = (provider or settings.DEFAULT_PROVIDER).lower()
    if provider == "ollama":
        return await fetch_ollama_models(base_url)
    if provider == "openai":
        return await fetch_openai_models(base_url)
    # Anthropic and others don't expose a simple list endpoint here.
    return {"available": bool(settings.ANTHROPIC_API_KEY) if provider == "anthropic" else False,
            "models": [], "base_url": base_url or "", "error": None}


# Approximate USD pricing per 1K tokens (prompt, completion). Local models are
# free; cloud entries let the same cost-tracking code work unchanged if a key
# is added later.
PRICING: dict[str, tuple[float, float]] = {
    # provider:model -> (prompt_per_1k, completion_per_1k)
    "openai:gpt-4o-mini": (0.00015, 0.0006),
    "openai:gpt-4o": (0.0025, 0.01),
    "anthropic:claude-3-5-haiku-latest": (0.0008, 0.004),
    "anthropic:claude-sonnet-4-5": (0.003, 0.015),
}


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


def estimate_cost(provider: str, model: str, usage: Usage) -> float:
    rate = PRICING.get(f"{provider}:{model}")
    if not rate:
        return 0.0  # local / unknown model -> free
    prompt_rate, completion_rate = rate
    return round(
        (usage.prompt_tokens / 1000) * prompt_rate
        + (usage.completion_tokens / 1000) * completion_rate,
        6,
    )


def build_chat_model(
    provider: str,
    model: str,
    temperature: float = 0.7,
    thinking: bool | None = None,
) -> BaseChatModel:
    """Instantiate a chat model for the given provider/model.

    ``thinking`` toggles Qwen/vLLM reasoning per call; ``None`` falls back to the
    global ``ENABLE_THINKING`` default. Only applied to OpenAI-compatible gateways.
    """
    provider = (provider or settings.DEFAULT_PROVIDER).lower()

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=model or settings.DEFAULT_MODEL,
            base_url=_ollama_base_url,
            temperature=temperature,
            # Keep responses snappy and bounded for the demo.
            num_predict=1024,
        )

    if provider == "openai":
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is not set")
        from langchain_openai import ChatOpenAI  # type: ignore

        kwargs: dict = {
            "model": model,
            "temperature": temperature,
            "api_key": settings.OPENAI_API_KEY,
            "timeout": settings.OPENAI_TIMEOUT,
            # Include token usage in the streamed response (stream_options).
            "stream_usage": True,
        }
        # Custom OpenAI-compatible gateway (vLLM, hosted Qwen, etc.).
        if settings.OPENAI_BASE_URL:
            kwargs["base_url"] = settings.OPENAI_BASE_URL
            # Toggle Qwen/vLLM reasoning ("thinking") per request. Off by default
            # keeps responses short/fast and avoids reasoning-driven 524 timeouts.
            enable_thinking = settings.ENABLE_THINKING if thinking is None else bool(thinking)
            kwargs["extra_body"] = {
                "chat_template_kwargs": {"enable_thinking": enable_thinking}
            }
        return ChatOpenAI(**kwargs)

    if provider == "anthropic":
        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        from langchain_anthropic import ChatAnthropic  # type: ignore

        return ChatAnthropic(
            model=model, temperature=temperature, api_key=settings.ANTHROPIC_API_KEY
        )

    raise ValueError(f"Unknown provider: {provider!r}")


def extract_usage(message) -> Usage:
    """Pull token usage out of a LangChain AIMessage across providers."""
    # LangChain normalises this into ``usage_metadata`` for most providers.
    meta = getattr(message, "usage_metadata", None)
    if meta:
        return Usage(
            prompt_tokens=int(meta.get("input_tokens", 0) or 0),
            completion_tokens=int(meta.get("output_tokens", 0) or 0),
        )
    # Ollama also exposes counts under response_metadata.
    rmeta = getattr(message, "response_metadata", {}) or {}
    return Usage(
        prompt_tokens=int(rmeta.get("prompt_eval_count", 0) or 0),
        completion_tokens=int(rmeta.get("eval_count", 0) or 0),
    )


def list_providers() -> list[dict]:
    """Report available providers + a few suggested models for the UI."""
    return [
        {
            "name": "ollama",
            "models": ["qwen2.5", "llama3.1", "mistral", "phi3"],
            "available": True,  # assumed running locally
        },
        {
            # Also covers OpenAI-compatible gateways via OPENAI_BASE_URL.
            "name": "openai",
            "models": [settings.DEFAULT_MODEL] if settings.OPENAI_BASE_URL else ["gpt-4o-mini", "gpt-4o"],
            "available": bool(settings.OPENAI_API_KEY),
        },
        {
            "name": "anthropic",
            "models": ["claude-3-5-haiku-latest", "claude-sonnet-4-5"],
            "available": bool(settings.ANTHROPIC_API_KEY),
        },
    ]
