"""Test fixtures.

The whole suite runs offline: a temp SQLite DB replaces Postgres and a fake chat
model replaces Ollama, so the critical paths (agent CRUD, workflow execution,
feedback loops, channel message delivery) are exercised with zero external deps.
"""
from __future__ import annotations

import os
import pathlib

# Configure the environment BEFORE importing app modules (settings is cached).
_TEST_DB = pathlib.Path(__file__).parent / "_test.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_DB.as_posix()}"
os.environ["REDIS_URL"] = ""
os.environ["ENABLE_TELEGRAM"] = "false"

import pytest  # noqa: E402
from langchain_core.messages import AIMessage  # noqa: E402

from app.core.database import Base, SessionLocal, engine, init_db  # noqa: E402


class FakeChatModel:
    """Deterministic stand-in for a LangChain chat model.

    ``responder`` maps the system prompt (lowercased) to the text the model
    should return, enabling per-agent scripted behaviour (incl. loop control).
    Tracks call counts so tests can script "REVISE then APPROVED" feedback loops.
    """

    def __init__(self, responder, counter):
        self._responder = responder
        self._counter = counter

    def bind_tools(self, tools):  # tools ignored in tests
        return self

    async def ainvoke(self, messages):
        system = messages[0].content.lower() if messages else ""
        human = messages[-1].content if messages else ""
        text = self._responder(system, human, self._counter)
        return AIMessage(
            content=text,
            usage_metadata={"input_tokens": 11, "output_tokens": 7, "total_tokens": 18},
        )


@pytest.fixture(autouse=True)
async def _fresh_db():
    """Recreate all tables before each test for isolation."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await init_db()
    yield
    if _TEST_DB.exists():
        try:
            _TEST_DB.unlink()
        except PermissionError:
            pass


@pytest.fixture
async def session():
    async with SessionLocal() as s:
        yield s
        await s.commit()


@pytest.fixture
def fake_llm(monkeypatch):
    """Patch the engine's model factory with a scriptable fake.

    Returns a dict the test can populate: {"responder": fn, "counter": {}}.
    """
    state = {"counter": {}}

    def default_responder(system, human, counter):
        if "editor" in system:
            # First pass asks for changes, second approves -> exercises the loop.
            n = counter.get("editor", 0) + 1
            counter["editor"] = n
            return "REVISE: tighten the intro." if n == 1 else "APPROVED: final text."
        if "triage" in system:
            return "BILLING\nThe customer asks about a refund."
        return f"Response from agent (system mentions: {system[:20]})."

    state["responder"] = default_responder

    def factory(provider, model, temperature=0.7):
        return FakeChatModel(state["responder"], state["counter"])

    monkeypatch.setattr("app.runtime.engine.build_chat_model", factory)
    return state
