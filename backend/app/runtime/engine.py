"""The LangGraph workflow engine — where agent logic actually executes.

Why LangGraph (justified at length in the README): a workflow here is literally
a directed graph with conditional edges and cycles, which is exactly what
LangGraph's ``StateGraph`` models. Conditions map to ``add_conditional_edges``;
feedback loops map to edges that point backwards (guarded by per-node visit
limits); async execution and token streaming are first-class.

Responsibilities of this module:
  * Compile a stored workflow graph (nodes + conditioned edges) into a
    LangGraph ``StateGraph``.
  * Build each agent node as a real ReAct-style tool loop over a pluggable LLM.
  * Emit live monitoring events and persist every message + token/cost figure
    through an injected ``RunContext`` (keeps DB concerns out of the graph).
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.graph import END, START, StateGraph

from app.core.config import settings
from app.core.events import Event, get_event_bus
from app.core.logging import get_logger
from app.runtime.providers import (
    Usage,
    build_chat_model,
    estimate_cost,
    extract_usage,
)
from app.runtime.state import GraphState
from app.runtime.tools import get_tools
from app.runtime.tools import TOOL_REGISTRY

logger = get_logger(__name__)


class RunContext:
    """Side-channel for a single run: event emission, persistence, accounting.

    The graph nodes call into this so the graph itself stays pure. Implemented
    against callbacks rather than the DB directly to keep the engine testable.
    """

    def __init__(
        self,
        run_id: str,
        workflow_id: str | None,
        on_event: Callable[[Event], "asyncio.Future | Any"] | None = None,
        on_message: Callable[..., "asyncio.Future | Any"] | None = None,
        on_usage: Callable[..., "asyncio.Future | Any"] | None = None,
    ) -> None:
        self.run_id = run_id
        self.workflow_id = workflow_id
        self._bus = get_event_bus()
        self._on_event = on_event
        self._on_message = on_message
        self._on_usage = on_usage

    async def emit(
        self,
        type: str,
        *,
        agent_id: str | None = None,
        agent_name: str | None = None,
        data: dict | None = None,
    ) -> None:
        event = Event(
            type=type,
            run_id=self.run_id,
            workflow_id=self.workflow_id,
            agent_id=agent_id,
            agent_name=agent_name,
            data=data or {},
        )
        await self._bus.publish(event)
        if self._on_event:
            await _maybe_await(self._on_event(event))

    async def save_message(self, **kwargs) -> None:
        if self._on_message:
            await _maybe_await(self._on_message(**kwargs))

    async def add_usage(self, usage: Usage, cost: float) -> None:
        if self._on_usage:
            await _maybe_await(self._on_usage(usage, cost))


async def _maybe_await(value):
    if asyncio.iscoroutine(value):
        return await value
    return value


def _render_transcript(turns: list[dict], limit: int) -> str:
    if not turns:
        return "(no prior messages)"
    recent = turns[-limit:] if limit else turns
    return "\n".join(f"[{t['sender']}]: {t['content']}" for t in recent)


def _apply_guardrails(text: str, guardrails: dict) -> str:
    blocked = guardrails.get("blocked_words") or []
    cleaned = text
    for word in blocked:
        if word:
            cleaned = cleaned.replace(word, "[redacted]")
    return cleaned


async def _run_agent_turn(
    agent: dict,
    task: str,
    transcript: list[dict],
    ctx: RunContext,
    node_id: str,
) -> tuple[str, Usage]:
    """Execute one agent's reasoning/tool loop and return (final_text, usage)."""
    guardrails = agent.get("guardrails") or {}
    memory = agent.get("memory") or {}
    max_steps = int(guardrails.get("max_steps", 8) or 8)
    window = int(memory.get("max_messages", 20) or 20) if memory.get("enabled", True) else 2

    tools = get_tools(agent.get("tools") or [])
    model = build_chat_model(
        agent.get("provider", "ollama"),
        agent.get("model", settings.DEFAULT_MODEL),
        float(agent.get("temperature", 0.7)),
        thinking=agent.get("thinking"),
    )
    if tools:
        model = model.bind_tools(tools)

    system_text = (
        f"You are {agent['name']}, {agent.get('role') or 'an AI agent'}.\n"
        f"{agent.get('system_prompt', '')}\n\n"
        "You are one agent in a collaborative multi-agent workflow. Read the "
        "conversation so far and contribute your part concisely. If you use a "
        "tool, wait for its result before answering."
    )
    human_text = (
        f"Overall task: {task}\n\n"
        f"Conversation so far:\n{_render_transcript(transcript, window)}\n\n"
        f"Now respond as {agent['name']}."
    )
    messages: list = [SystemMessage(content=system_text), HumanMessage(content=human_text)]

    total = Usage()
    final_text = ""
    for _ in range(max_steps):
        # Stream the response so the HTTP connection keeps producing bytes —
        # this prevents Cloudflare/proxy read-timeouts (HTTP 524) on long
        # reasoning generations. LangChain aggregates chunks (content, tool
        # calls, usage) when AIMessageChunks are added together.
        response = None
        async for chunk in model.astream(messages):
            response = chunk if response is None else response + chunk
        if response is None:
            break

        u = extract_usage(response)
        total.prompt_tokens += u.prompt_tokens
        total.completion_tokens += u.completion_tokens

        tool_calls = getattr(response, "tool_calls", None) or []
        if tool_calls:
            messages.append(response)
            for call in tool_calls:
                name = call.get("name")
                args = call.get("args", {})
                await ctx.emit(
                    "tool_call",
                    agent_id=agent.get("id"),
                    agent_name=agent["name"],
                    data={"tool": name, "args": args, "node_id": node_id},
                )
                tool = TOOL_REGISTRY.get(name)
                if tool is None:
                    result = f"Unknown tool: {name}"
                else:
                    try:
                        result = await asyncio.to_thread(tool.invoke, args)
                    except Exception as exc:  # tool failure shouldn't kill the run
                        result = f"Tool {name} errored: {exc}"
                await ctx.emit(
                    "tool_result",
                    agent_id=agent.get("id"),
                    agent_name=agent["name"],
                    data={"tool": name, "result": str(result)[:500], "node_id": node_id},
                )
                messages.append(
                    ToolMessage(content=str(result), tool_call_id=call.get("id", name))
                )
            continue

        final_text = response.content if isinstance(response.content, str) else str(response.content)
        break

    final_text = _apply_guardrails(final_text or "(no response)", guardrails)
    return final_text, total


def build_agent_node(node: dict, agents_by_id: dict[str, dict], ctx: RunContext):
    """Create the async LangGraph node function for an agent node."""
    node_id = node["id"]
    agent_id = node.get("data", {}).get("agent_id")

    async def node_fn(state: GraphState) -> dict:
        agent = agents_by_id.get(agent_id)
        if agent is None:
            return {
                "last_output": f"(node {node_id} has no agent assigned)",
                "last_node": node_id,
                "steps": state.get("steps", 0) + 1,
            }

        visits = dict(state.get("visits") or {})
        visits[node_id] = visits.get(node_id, 0) + 1
        steps = state.get("steps", 0) + 1

        await ctx.emit(
            "node_start",
            agent_id=agent.get("id"),
            agent_name=agent["name"],
            data={"node_id": node_id, "visit": visits[node_id]},
        )

        task = state.get("input", "")
        transcript = list(state.get("transcript") or [])
        final_text, usage = await _run_agent_turn(agent, task, transcript, ctx, node_id)

        cost = estimate_cost(agent.get("provider", "ollama"), agent.get("model", ""), usage)
        await ctx.add_usage(usage, cost)
        await ctx.save_message(
            role="assistant",
            sender=agent["name"],
            recipient="workflow",
            agent_id=agent.get("id"),
            node_id=node_id,
            channel="internal",
            content=final_text,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
        )
        await ctx.emit(
            "agent_message",
            agent_id=agent.get("id"),
            agent_name=agent["name"],
            data={
                "node_id": node_id,
                "content": final_text,
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "cost_usd": cost,
            },
        )
        await ctx.emit(
            "node_end",
            agent_id=agent.get("id"),
            agent_name=agent["name"],
            data={"node_id": node_id},
        )

        new_turn = {
            "sender": agent["name"],
            "node_id": node_id,
            "content": final_text,
            "role": "assistant",
        }
        return {
            "transcript": [new_turn],
            "last_output": final_text,
            "last_node": node_id,
            "visits": visits,
            "steps": steps,
        }

    return node_fn


def _classify_nodes(graph: dict) -> tuple[dict, set, set]:
    """Return (agent_nodes_by_id, start_node_ids, end_node_ids)."""
    agent_nodes: dict[str, dict] = {}
    start_ids: set[str] = set()
    end_ids: set[str] = set()
    for node in graph.get("nodes", []):
        kind = node.get("data", {}).get("kind", "agent")
        if kind == "start":
            start_ids.add(node["id"])
        elif kind == "end":
            end_ids.add(node["id"])
        else:
            agent_nodes[node["id"]] = node
    return agent_nodes, start_ids, end_ids


def _make_router(
    node_id: str,
    edges: list[dict],
    agent_node_ids: set[str],
    end_ids: set[str],
    max_visits: dict[str, int],
    ctx: RunContext,
    name_of,
):
    """Build the conditional-edge router for one source node.

    Specific conditions are evaluated before unconditional (``always``) edges so
    ``always`` acts as a fallback. Backward edges (loops) are skipped once their
    target's visit cap is hit, which makes feedback loops terminate.

    The router is async so it can emit a ``route`` monitoring event describing
    the edge taken (e.g. "Editor → Writer (REVISE)"), which the UI renders as an
    arrow in the live trace.
    """
    outgoing = [e for e in edges if e["source"] == node_id]
    ordered = sorted(
        outgoing,
        key=lambda e: 0 if e.get("condition", {}).get("when", "always") != "always" else 1,
    )

    async def _emit_route(
        to_node: str, when: str, value, reason: str | None = None,
        blocked_loop: str | None = None,
    ) -> None:
        to_name = "END" if to_node == END else name_of(to_node)
        data = {
            "from_node": node_id,
            "from_name": name_of(node_id),
            "to_node": to_node,
            "to_name": to_name,
            "when": when,
            "value": value,
            "reason": reason,
        }
        # A loop-back edge was wanted but skipped because the target hit its
        # visit cap — record which draft node so the run can return its best draft.
        if blocked_loop:
            data["blocked_loop_target"] = blocked_loop
            data["blocked_loop_name"] = name_of(blocked_loop)
            data["reason"] = data.get("reason") or "max_visits"
        await ctx.emit("route", agent_name=name_of(node_id), data=data)

    async def router(state: GraphState) -> str:
        if state.get("steps", 0) >= settings.MAX_WORKFLOW_STEPS:
            await _emit_route(END, "always", None, reason="max_steps")
            return END
        last = (state.get("last_output") or "").lower()
        visits = state.get("visits") or {}
        blocked_loop: str | None = None
        for edge in ordered:
            target = edge["target"]
            cond = edge.get("condition", {}) or {}
            when = cond.get("when", "always")
            value = (cond.get("value") or "").lower()

            # Loop guard: don't re-enter an agent node past its visit cap. Remember
            # it so we can surface "max revisions reached" and return its draft.
            if target in agent_node_ids and visits.get(target, 0) >= max_visits.get(target, 3):
                blocked_loop = target
                continue

            matched = (
                when == "always"
                or (when == "contains" and value and value in last)
                or (when == "not_contains" and value and value not in last)
                or (when == "llm_route" and value and value in last)
            )
            if matched:
                resolved = END if target in end_ids else target
                await _emit_route(
                    resolved, when, cond.get("value"),
                    blocked_loop=blocked_loop if resolved == END else None,
                )
                return resolved
        await _emit_route(END, "always", None, reason="no_match", blocked_loop=blocked_loop)
        return END

    return router


def compile_workflow(
    graph: dict,
    agents_by_id: dict[str, dict],
    ctx: RunContext,
):
    """Compile a stored workflow graph into an executable LangGraph app."""
    agent_nodes, start_ids, end_ids = _classify_nodes(graph)
    if not agent_nodes:
        raise ValueError("Workflow has no agent nodes to execute.")

    edges = graph.get("edges", [])
    agent_node_ids = set(agent_nodes.keys())
    max_visits = {
        nid: int(n.get("data", {}).get("max_visits", 3) or 3)
        for nid, n in agent_nodes.items()
    }

    # Readable name for each node (agent name), for arrow-style route events.
    def name_of(nid: str) -> str:
        node = agent_nodes.get(nid)
        if node:
            agent = agents_by_id.get(node.get("data", {}).get("agent_id"))
            if agent:
                return agent["name"]
            return node.get("data", {}).get("label") or nid
        return nid

    builder = StateGraph(GraphState)
    for nid, node in agent_nodes.items():
        builder.add_node(nid, build_agent_node(node, agents_by_id, ctx))

    # Resolve the entry agent node.
    entry = _resolve_entry(agent_nodes, edges, start_ids)
    builder.add_edge(START, entry)

    # Wire conditional edges out of every agent node.
    for nid in agent_nodes:
        router = _make_router(nid, edges, agent_node_ids, end_ids, max_visits, ctx, name_of)
        builder.add_conditional_edges(nid, router)

    return builder.compile()


def _resolve_entry(agent_nodes: dict, edges: list[dict], start_ids: set[str]) -> str:
    # If there's an explicit start node, follow its first edge into an agent.
    for edge in edges:
        if edge["source"] in start_ids and edge["target"] in agent_nodes:
            return edge["target"]
    # Otherwise pick an agent node with no incoming edge from another agent node.
    targets_with_incoming = {
        e["target"] for e in edges if e["source"] in agent_nodes
    }
    for nid in agent_nodes:
        if nid not in targets_with_incoming:
            return nid
    # Fallback: first node (handles single-node or fully-cyclic graphs).
    return next(iter(agent_nodes))


async def execute_workflow(
    graph: dict,
    agents_by_id: dict[str, dict],
    user_input: str,
    ctx: RunContext,
) -> GraphState:
    """Compile and run a workflow to completion, returning the final state."""
    app = compile_workflow(graph, agents_by_id, ctx)
    initial: GraphState = {
        "input": user_input,
        "transcript": [],
        "last_output": "",
        "last_node": "",
        "visits": {},
        "steps": 0,
    }
    config = {"recursion_limit": settings.MAX_WORKFLOW_STEPS + 5}
    final_state = await app.ainvoke(initial, config=config)
    return final_state


async def run_single_agent(
    agent: dict,
    user_input: str,
    history: list[dict],
    ctx: RunContext,
) -> tuple[str, Usage]:
    """Run one agent directly (used by messaging channels for live chat)."""
    await ctx.emit(
        "node_start",
        agent_id=agent.get("id"),
        agent_name=agent["name"],
        data={"node_id": "chat"},
    )
    text, usage = await _run_agent_turn(agent, user_input, history, ctx, "chat")
    cost = estimate_cost(agent.get("provider", "ollama"), agent.get("model", ""), usage)
    await ctx.add_usage(usage, cost)
    await ctx.emit(
        "agent_message",
        agent_id=agent.get("id"),
        agent_name=agent["name"],
        data={
            "node_id": "chat",
            "content": text,
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "cost_usd": cost,
        },
    )
    return text, usage
