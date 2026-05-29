"""Pre-built workflow templates.

Each template is a declarative spec: a set of agents (referenced locally by a
short key) plus a graph of nodes and conditioned edges. ``instantiate`` creates
the real agents, maps the local keys to their new ids, and builds a workflow
whose graph wires those agents together.

To add a template: append a ``TemplateSpec`` to ``TEMPLATES``. It immediately
becomes listable and instantiable from the UI — no other code changes needed.
(See README → "Adding a workflow template".)
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Agent, Workflow


@dataclass
class AgentSpec:
    ref: str  # local key used inside the template's graph
    name: str
    role: str
    system_prompt: str
    tools: list[str] = field(default_factory=list)
    channels: list[str] = field(default_factory=list)
    model: str = field(default_factory=lambda: settings.DEFAULT_MODEL)


@dataclass
class NodeSpec:
    id: str
    kind: str  # start | agent | end
    ref: str | None = None  # agent ref for kind == "agent"
    label: str = ""
    x: float = 0
    y: float = 0
    max_visits: int = 3


@dataclass
class EdgeSpec:
    source: str
    target: str
    when: str = "always"
    value: str | None = None
    label: str = ""


@dataclass
class TemplateSpec:
    key: str
    name: str
    description: str
    agents: list[AgentSpec]
    nodes: list[NodeSpec]
    edges: list[EdgeSpec]


# --------------------------------------------------------------------------- #
# Template 1 — Research → Write → Edit, with an editorial feedback loop.
# --------------------------------------------------------------------------- #
RESEARCH_WRITE = TemplateSpec(
    key="research_write",
    name="Research & Write (with feedback loop)",
    description=(
        "A Researcher gathers facts with web search, a Writer drafts an article, "
        "and an Editor reviews it. If the Editor asks for changes, the draft loops "
        "back to the Writer until approved — demonstrating conditional feedback loops."
    ),
    agents=[
        AgentSpec(
            ref="researcher",
            name="Researcher",
            role="research analyst",
            tools=["web_search", "http_get"],
            system_prompt=(
                "Gather accurate, up-to-date facts on the requested topic using the "
                "web_search tool. Summarise the 4-6 most important findings as bullet "
                "points with sources. Be factual and concise."
            ),
        ),
        AgentSpec(
            ref="writer",
            name="Writer",
            role="content writer",
            system_prompt=(
                "Using the researcher's findings (and any editor feedback in the "
                "conversation), write a clear, engaging ~200-word article. If the "
                "editor requested changes, revise accordingly."
            ),
        ),
        AgentSpec(
            ref="editor",
            name="Editor",
            role="editor-in-chief",
            system_prompt=(
                "Review the latest draft for accuracy, clarity and structure. If it is "
                "publishable, reply starting with the single word APPROVED followed by "
                "the final text. If not, reply starting with REVISE and give specific, "
                "actionable feedback for the writer."
            ),
        ),
    ],
    nodes=[
        NodeSpec(id="start", kind="start", label="Start", x=0, y=120),
        NodeSpec(id="n_researcher", kind="agent", ref="researcher", label="Researcher", x=200, y=120),
        NodeSpec(id="n_writer", kind="agent", ref="writer", label="Writer", x=440, y=120, max_visits=5),
        NodeSpec(id="n_editor", kind="agent", ref="editor", label="Editor", x=680, y=120, max_visits=5),
        NodeSpec(id="end", kind="end", label="End", x=920, y=120),
    ],
    edges=[
        EdgeSpec("start", "n_researcher", "always", label="begin"),
        EdgeSpec("n_researcher", "n_writer", "always", label="findings"),
        EdgeSpec("n_writer", "n_editor", "always", label="draft"),
        # Feedback loop: Editor asks to REVISE -> back to Writer.
        EdgeSpec("n_editor", "n_writer", "contains", value="REVISE", label="needs changes"),
        # Otherwise (APPROVED / fallback) -> finish.
        EdgeSpec("n_editor", "end", "always", label="approved"),
    ],
)


# --------------------------------------------------------------------------- #
# Template 2 — Support triage with conditional routing (Telegram-facing).
# --------------------------------------------------------------------------- #
SUPPORT_TRIAGE = TemplateSpec(
    key="support_triage",
    name="Customer Support Triage (Telegram)",
    description=(
        "A Telegram-facing Triage agent classifies an incoming request and routes it "
        "conditionally to either a Billing specialist or a Technical engineer, who "
        "produces the final answer — demonstrating conditional branching across agents."
    ),
    agents=[
        AgentSpec(
            ref="triage",
            name="Triage",
            role="support triage agent",
            channels=["telegram"],
            system_prompt=(
                "Classify the customer's request. Respond with exactly one word on the "
                "first line: BILLING (payments, invoices, refunds, subscriptions) or "
                "TECHNICAL (errors, bugs, how-to, integrations). Then briefly restate "
                "the request for the specialist."
            ),
        ),
        AgentSpec(
            ref="billing",
            name="Billing Specialist",
            role="billing specialist",
            tools=["calculator"],
            system_prompt=(
                "You handle billing questions. Give a clear, friendly, accurate answer "
                "about payments, invoices, refunds or subscriptions. Use the calculator "
                "tool for any arithmetic."
            ),
        ),
        AgentSpec(
            ref="technical",
            name="Technical Engineer",
            role="technical support engineer",
            tools=["web_search"],
            system_prompt=(
                "You handle technical questions. Give a clear, step-by-step solution. "
                "Use web_search if you need current technical details."
            ),
        ),
    ],
    nodes=[
        NodeSpec(id="start", kind="start", label="Start", x=0, y=160),
        NodeSpec(id="n_triage", kind="agent", ref="triage", label="Triage", x=200, y=160),
        NodeSpec(id="n_billing", kind="agent", ref="billing", label="Billing", x=460, y=60),
        NodeSpec(id="n_technical", kind="agent", ref="technical", label="Technical", x=460, y=260),
        NodeSpec(id="end", kind="end", label="End", x=720, y=160),
    ],
    edges=[
        EdgeSpec("start", "n_triage", "always", label="incoming"),
        EdgeSpec("n_triage", "n_billing", "contains", value="BILLING", label="billing"),
        EdgeSpec("n_triage", "n_technical", "always", label="technical / default"),
        EdgeSpec("n_billing", "end", "always", label="answer"),
        EdgeSpec("n_technical", "end", "always", label="answer"),
    ],
)


TEMPLATES: dict[str, TemplateSpec] = {
    RESEARCH_WRITE.key: RESEARCH_WRITE,
    SUPPORT_TRIAGE.key: SUPPORT_TRIAGE,
}


def list_templates() -> list[dict]:
    return [
        {
            "key": t.key,
            "name": t.name,
            "description": t.description,
            "agent_count": len(t.agents),
        }
        for t in TEMPLATES.values()
    ]


async def instantiate(session: AsyncSession, key: str) -> Workflow:
    """Create the template's agents + a workflow wiring them together."""
    spec = TEMPLATES.get(key)
    if spec is None:
        raise KeyError(f"Unknown template: {key}")

    # Create agents, remembering ref -> new agent id.
    ref_to_id: dict[str, str] = {}
    for a in spec.agents:
        agent = Agent(
            name=a.name,
            role=a.role,
            system_prompt=a.system_prompt,
            model=a.model,
            tools=a.tools,
            channels=a.channels,
            memory={"enabled": True, "max_messages": 20},
            guardrails={"max_steps": 6, "blocked_words": []},
        )
        session.add(agent)
        await session.flush()
        ref_to_id[a.ref] = agent.id

    nodes = [
        {
            "id": n.id,
            "type": "agentNode",
            "position": {"x": n.x, "y": n.y},
            "data": {
                "label": n.label,
                "kind": n.kind,
                "agent_id": ref_to_id.get(n.ref) if n.ref else None,
                "max_visits": n.max_visits,
                "position": {"x": n.x, "y": n.y},
            },
        }
        for n in spec.nodes
    ]
    edges = [
        {
            "id": f"e_{i}",
            "source": e.source,
            "target": e.target,
            "condition": {"when": e.when, "value": e.value, "label": e.label},
        }
        for i, e in enumerate(spec.edges)
    ]

    workflow = Workflow(
        name=spec.name,
        description=spec.description,
        graph={"nodes": nodes, "edges": edges},
        is_template=True,
        template_key=spec.key,
    )
    session.add(workflow)
    await session.flush()
    await session.refresh(workflow)
    return workflow
