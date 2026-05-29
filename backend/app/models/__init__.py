"""SQLAlchemy ORM models — the persistence layer.

Design notes
------------
* UUID string primary keys keep ids portable across SQLite and Postgres.
* Rich, free-form configuration (guardrails, memory, schedules, the workflow
  graph itself) is stored as JSON so the *shape* of agent/workflow config can
  evolve without migrations — the platform's whole value proposition is
  "configurable dimensions", and JSON keeps that open-ended.
* ``Message`` is the single source of truth for both inter-agent messages and
  human<->agent channel messages, so the UI can show one unified history.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.core.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(200), default="")
    system_prompt: Mapped[str] = mapped_column(Text, default="")

    # Model configuration (defaults follow the configured provider/model)
    provider: Mapped[str] = mapped_column(String(40), default=lambda: settings.DEFAULT_PROVIDER)
    model: Mapped[str] = mapped_column(String(120), default=lambda: settings.DEFAULT_MODEL)
    temperature: Mapped[float] = mapped_column(Float, default=0.7)
    # Qwen/vLLM reasoning ("thinking") mode for this agent. Off by default.
    thinking: Mapped[bool] = mapped_column(default=False, nullable=True)

    # Capability / behaviour configuration (all the "configurable dimensions")
    tools: Mapped[list] = mapped_column(JSON, default=list)        # tool names
    channels: Mapped[list] = mapped_column(JSON, default=list)     # e.g. ["telegram"]
    skills: Mapped[list] = mapped_column(JSON, default=list)       # free-form skill tags
    memory: Mapped[dict] = mapped_column(JSON, default=dict)       # {enabled, max_messages}
    schedule: Mapped[dict] = mapped_column(JSON, default=dict)     # {cron, enabled}
    interaction_rules: Mapped[dict] = mapped_column(JSON, default=dict)
    guardrails: Mapped[dict] = mapped_column(JSON, default=dict)   # {max_tokens, blocked_words, max_steps}

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")

    # The visual graph: {"nodes": [...], "edges": [...]}.
    # Nodes reference agent ids; edges carry conditions (incl. feedback loops).
    graph: Mapped[dict] = mapped_column(JSON, default=dict)

    # Marks templates seeded by the platform vs. user-created workflows.
    is_template: Mapped[bool] = mapped_column(default=False)
    template_key: Mapped[str | None] = mapped_column(String(80), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    runs: Mapped[list["WorkflowRun"]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan"
    )


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workflow_id: Mapped[str] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), index=True
    )

    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|running|completed|failed
    trigger: Mapped[str] = mapped_column(String(40), default="manual")  # manual|telegram|schedule
    input: Mapped[dict] = mapped_column(JSON, default=dict)
    output: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Aggregated token/cost accounting for the whole run.
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    step_count: Mapped[int] = mapped_column(Integer, default=0)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    workflow: Mapped["Workflow"] = relationship(back_populates="runs")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class Message(Base):
    """Unified message log: inter-agent messages AND human<->agent channel turns."""

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="CASCADE"), index=True, nullable=True
    )

    # role: user | assistant | system | tool
    role: Mapped[str] = mapped_column(String(20), default="assistant")
    # Logical sender/recipient. For agents these are agent names; for humans,
    # the channel identity (e.g. "telegram:<chat_id>").
    sender: Mapped[str] = mapped_column(String(160), default="")
    recipient: Mapped[str] = mapped_column(String(160), default="")

    agent_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    channel: Mapped[str | None] = mapped_column(String(40), nullable=True)  # telegram|internal
    node_id: Mapped[str | None] = mapped_column(String(80), nullable=True)

    content: Mapped[str] = mapped_column(Text, default="")
    extra: Mapped[dict] = mapped_column(JSON, default=dict)  # tool calls, citations, etc.

    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    run: Mapped["WorkflowRun | None"] = relationship(back_populates="messages")


class LogEvent(Base):
    """Persisted copy of monitoring events, so the live log survives reloads."""

    __tablename__ = "log_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    run_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    type: Mapped[str] = mapped_column(String(40))
    agent_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Setting(Base):
    """Tiny key/value store for runtime-tunable settings (e.g. Ollama URL).

    Persisted so UI changes survive restarts; loaded into the runtime on startup.
    """

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class ChannelBinding(Base):
    """Connects an external messaging channel to an agent or workflow."""

    __tablename__ = "channel_bindings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    channel: Mapped[str] = mapped_column(String(40), default="telegram")
    agent_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    workflow_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    enabled: Mapped[bool] = mapped_column(default=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
