"""Critical path: message delivery through a messaging channel.

Drives the shared inbound router the Telegram adapter uses, so it validates
binding resolution, agent execution, reply generation, and history persistence
without needing a real Telegram connection.
"""
from __future__ import annotations

from app.channels.router import handle_inbound
from app.models import ChannelBinding
from app.schemas import AgentCreate
from app.services import agent_service, message_service


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
