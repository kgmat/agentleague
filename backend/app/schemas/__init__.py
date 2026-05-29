"""Pydantic schemas — the API contract between frontend and backend.

Kept separate from ORM models so the wire format can differ from storage and
so validation lives in one place.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings


# --------------------------------------------------------------------------- #
# Agents
# --------------------------------------------------------------------------- #
class MemoryConfig(BaseModel):
    enabled: bool = True
    max_messages: int = 20  # rolling window of recent turns kept as context


class ScheduleConfig(BaseModel):
    enabled: bool = False
    cron: str | None = None  # informational; surfaced in UI


class Guardrails(BaseModel):
    max_steps: int = 8          # max LLM/tool turns inside a single agent node
    max_tokens: int | None = None
    blocked_words: list[str] = Field(default_factory=list)


class AgentBase(BaseModel):
    name: str
    role: str = ""
    system_prompt: str = ""
    provider: str = Field(default_factory=lambda: settings.DEFAULT_PROVIDER)
    model: str = Field(default_factory=lambda: settings.DEFAULT_MODEL)
    temperature: float = 0.7
    thinking: bool = False  # Qwen/vLLM reasoning mode (per agent)
    tools: list[str] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    interaction_rules: dict[str, Any] = Field(default_factory=dict)
    guardrails: Guardrails = Field(default_factory=Guardrails)


class AgentCreate(AgentBase):
    pass


class AgentUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    system_prompt: str | None = None
    provider: str | None = None
    model: str | None = None
    temperature: float | None = None
    thinking: bool | None = None
    tools: list[str] | None = None
    channels: list[str] | None = None
    skills: list[str] | None = None
    memory: MemoryConfig | None = None
    schedule: ScheduleConfig | None = None
    interaction_rules: dict[str, Any] | None = None
    guardrails: Guardrails | None = None


class AgentOut(AgentBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# Workflows (visual graph)
# --------------------------------------------------------------------------- #
class NodeData(BaseModel):
    """UI-facing data attached to a React Flow node."""

    label: str = ""
    agent_id: str | None = None
    kind: Literal["agent", "start", "end"] = "agent"
    # Per-node override: how many times a node may be visited (feedback-loop guard)
    max_visits: int = 3
    position: dict[str, float] = Field(default_factory=lambda: {"x": 0, "y": 0})


class GraphNode(BaseModel):
    id: str
    type: str = "agentNode"
    data: NodeData = Field(default_factory=NodeData)
    position: dict[str, float] = Field(default_factory=lambda: {"x": 0, "y": 0})


class EdgeCondition(BaseModel):
    """Condition controlling whether an edge is taken.

    when:
      * "always"        — unconditional edge
      * "contains"      — last output contains ``value`` (case-insensitive)
      * "not_contains"  — last output does NOT contain ``value``
      * "llm_route"     — handled by the source node's router label match
    """

    when: Literal["always", "contains", "not_contains", "llm_route"] = "always"
    value: str | None = None
    label: str | None = None  # human-readable, shown on the edge in the UI


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    condition: EdgeCondition = Field(default_factory=EdgeCondition)


class WorkflowGraph(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class WorkflowBase(BaseModel):
    name: str
    description: str = ""
    graph: WorkflowGraph = Field(default_factory=WorkflowGraph)


class WorkflowCreate(WorkflowBase):
    pass


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    graph: WorkflowGraph | None = None


class WorkflowOut(WorkflowBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    is_template: bool
    template_key: str | None
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# Runs & messages
# --------------------------------------------------------------------------- #
class RunCreate(BaseModel):
    input: str = ""
    trigger: str = "manual"


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    run_id: str | None
    role: str
    sender: str
    recipient: str
    agent_id: str | None
    channel: str | None
    node_id: str | None
    content: str
    extra: dict[str, Any]
    prompt_tokens: int
    completion_tokens: int
    created_at: datetime


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    workflow_id: str
    status: str
    trigger: str
    input: dict[str, Any]
    output: dict[str, Any]
    error: str | None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    step_count: int
    started_at: datetime
    finished_at: datetime | None


class RunDetail(RunOut):
    messages: list[MessageOut] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Templates, channels, tools, providers
# --------------------------------------------------------------------------- #
class TemplateOut(BaseModel):
    key: str
    name: str
    description: str
    agent_count: int


class ChannelBindingCreate(BaseModel):
    channel: str = "telegram"
    agent_id: str | None = None
    workflow_id: str | None = None
    enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)


class ChannelBindingOut(ChannelBindingCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime


class ToolInfo(BaseModel):
    name: str
    description: str


class ProviderInfo(BaseModel):
    name: str
    models: list[str]
    available: bool
