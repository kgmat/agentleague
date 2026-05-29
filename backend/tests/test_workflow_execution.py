"""Critical path: workflow execution, conditional routing, and feedback loops.

Uses the fake LLM, so this verifies the *graph/runtime* behaviour (ordering,
branching, loop termination, token accounting) independently of any model.
"""
from __future__ import annotations

from app.runtime.engine import RunContext, execute_workflow


def _agents():
    return {
        "researcher": {"id": "researcher", "name": "Researcher", "role": "researcher",
                       "system_prompt": "research", "provider": "ollama", "model": "x",
                       "temperature": 0.0, "tools": [], "guardrails": {"max_steps": 2}, "memory": {}},
        "writer": {"id": "writer", "name": "Writer", "role": "writer",
                   "system_prompt": "writer", "provider": "ollama", "model": "x",
                   "temperature": 0.0, "tools": [], "guardrails": {"max_steps": 2}, "memory": {}},
        "editor": {"id": "editor", "name": "Editor", "role": "editor",
                   "system_prompt": "editor", "provider": "ollama", "model": "x",
                   "temperature": 0.0, "tools": [], "guardrails": {"max_steps": 2}, "memory": {}},
        "triage": {"id": "triage", "name": "Triage", "role": "triage",
                   "system_prompt": "triage", "provider": "ollama", "model": "x",
                   "temperature": 0.0, "tools": [], "guardrails": {"max_steps": 2}, "memory": {}},
        "billing": {"id": "billing", "name": "Billing", "role": "billing",
                    "system_prompt": "billing", "provider": "ollama", "model": "x",
                    "temperature": 0.0, "tools": [], "guardrails": {"max_steps": 2}, "memory": {}},
        "technical": {"id": "technical", "name": "Technical", "role": "technical",
                      "system_prompt": "technical", "provider": "ollama", "model": "x",
                      "temperature": 0.0, "tools": [], "guardrails": {"max_steps": 2}, "memory": {}},
    }


def _node(nid, kind="agent", agent_id=None, max_visits=3):
    return {"id": nid, "data": {"kind": kind, "agent_id": agent_id, "max_visits": max_visits}}


def _edge(src, tgt, when="always", value=None):
    return {"source": src, "target": tgt, "condition": {"when": when, "value": value}}


def _capture_ctx():
    messages: list = []
    usage = {"prompt": 0, "completion": 0, "cost": 0.0}

    async def on_message(**kw):
        messages.append(kw)

    async def on_usage(u, cost):
        usage["prompt"] += u.prompt_tokens
        usage["completion"] += u.completion_tokens
        usage["cost"] += cost

    ctx = RunContext("run-test", "wf-test", on_message=on_message, on_usage=on_usage)
    return ctx, messages, usage


async def test_linear_workflow_runs_all_nodes(fake_llm):
    graph = {
        "nodes": [
            _node("start", "start"),
            _node("a", "agent", "researcher"),
            _node("b", "agent", "writer"),
            _node("end", "end"),
        ],
        "edges": [_edge("start", "a"), _edge("a", "b"), _edge("b", "end")],
    }
    ctx, messages, usage = _capture_ctx()
    state = await execute_workflow(graph, _agents(), "Write about otters", ctx)

    senders = [t["sender"] for t in state["transcript"]]
    assert senders == ["Researcher", "Writer"]
    assert len(messages) == 2
    assert usage["prompt"] > 0  # token accounting flowed through


async def test_feedback_loop_terminates(fake_llm):
    """Editor returns REVISE once then APPROVED; Writer must run twice."""
    graph = {
        "nodes": [
            _node("start", "start"),
            _node("w", "agent", "writer", max_visits=3),
            _node("e", "agent", "editor", max_visits=3),
            _node("end", "end"),
        ],
        "edges": [
            _edge("start", "w"),
            _edge("w", "e"),
            _edge("e", "w", "contains", "REVISE"),  # loop back on revise
            _edge("e", "end"),                        # fallback -> finish
        ],
    }
    ctx, messages, _ = _capture_ctx()
    state = await execute_workflow(graph, _agents(), "Draft a post", ctx)

    senders = [t["sender"] for t in state["transcript"]]
    assert senders.count("Writer") == 2  # looped exactly once
    assert senders.count("Editor") == 2
    assert "APPROVED" in state["last_output"]


async def test_conditional_routing_picks_branch(fake_llm):
    """Triage emits BILLING -> only the Billing branch should execute."""
    graph = {
        "nodes": [
            _node("start", "start"),
            _node("t", "agent", "triage"),
            _node("bill", "agent", "billing"),
            _node("tech", "agent", "technical"),
            _node("end", "end"),
        ],
        "edges": [
            _edge("start", "t"),
            _edge("t", "bill", "contains", "BILLING"),
            _edge("t", "tech"),  # default fallback
            _edge("bill", "end"),
            _edge("tech", "end"),
        ],
    }
    ctx, _, _ = _capture_ctx()
    state = await execute_workflow(graph, _agents(), "I want a refund", ctx)

    senders = [t["sender"] for t in state["transcript"]]
    assert "Billing" in senders
    assert "Technical" not in senders
