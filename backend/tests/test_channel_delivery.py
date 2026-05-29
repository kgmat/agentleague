"""Critical path: message delivery through a messaging channel.

Drives the shared inbound router the Telegram adapter uses, so it validates
binding resolution, agent execution, reply generation, and history persistence
without needing a real Telegram connection.
"""
from __future__ import annotations

from app.channels import outbound
from app.channels.router import handle_inbound
from app.models import Agent, ChannelBinding, Workflow, WorkflowRun
from app.schemas import AgentCreate
from app.services import agent_service, message_service, run_service


async def test_inbound_message_routes_to_bound_agent(session, fake_llm):
    agent = await agent_service.create_agent(
        session,
        AgentCreate(name="Support", role="support agent", system_prompt="help users"),
    )
    session.add(ChannelBinding(channel="telegram", agent_id=agent.id, enabled=True))
    await session.commit()

    reply = await handle_inbound("telegram", "chat-1", "Hello there")
    assert reply and "Response from agent" in reply

    # Both the human turn and the agent reply must be persisted + visible.
    history = await message_service.channel_history(session, "telegram", "telegram:chat-1")
    roles = [m.role for m in history]
    assert "user" in roles
    assert "assistant" in roles


async def test_unbound_channel_returns_helpful_message(session, fake_llm):
    reply = await handle_inbound("telegram", "chat-2", "anyone home?")
    assert "No agent or workflow" in reply


async def test_slack_channel_routes_to_bound_agent(session, fake_llm):
    """The router is channel-agnostic: Slack resolves bindings the same way."""
    agent = await agent_service.create_agent(session, AgentCreate(name="SlackBot", role="helper"))
    session.add(ChannelBinding(channel="slack", agent_id=agent.id, enabled=True))
    await session.commit()

    reply = await handle_inbound("slack", "C123", "hi there")
    assert reply and "Response from agent" in reply

    history = await message_service.channel_history(session, "slack", "slack:C123")
    assert any(m.role == "assistant" for m in history)


async def test_workflow_result_delivered_back_to_channel(session, fake_llm):
    """Channel→workflow runs in the background and delivers the result on completion."""
    agent = Agent(name="Solo", system_prompt="answer the request")
    session.add(agent)
    await session.flush()
    wf = Workflow(
        name="Solo WF",
        graph={
            "nodes": [
                {"id": "start", "data": {"kind": "start"}},
                {"id": "a", "data": {"kind": "agent", "agent_id": agent.id}},
                {"id": "end", "data": {"kind": "end"}},
            ],
            "edges": [
                {"source": "start", "target": "a", "condition": {"when": "always"}},
                {"source": "a", "target": "end", "condition": {"when": "always"}},
            ],
        },
    )
    session.add(wf)
    await session.flush()

    delivered: list = []

    async def fake_send(conversation, text, thread):
        delivered.append((conversation, text, thread))

    outbound.register_sender("slack", fake_send)
    try:
        run = await run_service.create_run(
            session, wf.id, "hello", trigger="slack",
            origin={"channel": "slack", "conversation": "C1", "thread": "t1", "identity": "slack:C1"},
        )
        await session.commit()
        await run_service._execute(run.id)
    finally:
        outbound.unregister_sender("slack")

    assert len(delivered) == 1
    conversation, text, thread = delivered[0]
    assert conversation == "C1" and thread == "t1"
    assert "Response from agent" in text


async def test_fail_orphaned_runs(session):
    wf = Workflow(name="W", graph={"nodes": [], "edges": []})
    session.add(wf)
    await session.flush()
    session.add(WorkflowRun(workflow_id=wf.id, status="running"))
    await session.commit()

    await run_service.fail_orphaned_runs()

    async with run_service.SessionLocal() as s:
        from sqlalchemy import select
        rows = (await s.execute(select(WorkflowRun))).scalars().all()
    assert all(r.status == "failed" for r in rows)
    assert all("Interrupted" in (r.error or "") for r in rows)
