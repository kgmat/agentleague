"""Shared inbound-message router used by every channel adapter.

Given a piece of inbound text from a human on some channel, this:
  1. resolves what the channel is bound to (a workflow or a single agent),
  2. runs the appropriate runtime path,
  3. persists both the human turn and the agent reply (visible in the UI),
  4. returns the reply text for the adapter to send back.

Binding resolution prefers a UI-configured ``ChannelBinding`` row, then falls
back to environment configuration, so the bot works out-of-the-box from .env
but can be repointed live from the web UI.
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.events import Event, get_event_bus
from app.core.logging import get_logger
from app.models import Agent, ChannelBinding, Workflow
from app.runtime.engine import RunContext, run_single_agent
from app.services import message_service, run_service
from app.services.agent_service import agent_to_dict

logger = get_logger(__name__)


# Per-channel environment fallbacks, used when no DB binding exists.
_ENV_FALLBACKS = {
    "telegram": lambda: (settings.TELEGRAM_WORKFLOW_ID, settings.TELEGRAM_AGENT_ID),
    "slack": lambda: (settings.SLACK_WORKFLOW_ID, settings.SLACK_AGENT_ID),
}


async def _resolve_binding(session, channel: str) -> tuple[str | None, str | None]:
    """Return (workflow_id, agent_id) the channel routes to.

    Prefers a UI-configured ``ChannelBinding`` (most recent enabled wins), then
    falls back to per-channel environment configuration.
    """
    result = await session.execute(
        select(ChannelBinding)
        .where(ChannelBinding.channel == channel)
        .where(ChannelBinding.enabled.is_(True))
        .order_by(ChannelBinding.created_at.desc())
    )
    binding = result.scalars().first()
    if binding:
        return binding.workflow_id, binding.agent_id
    fallback = _ENV_FALLBACKS.get(channel)
    return fallback() if fallback else (None, None)


async def handle_inbound(
    channel: str, sender_id: str, text: str, thread: str | None = None
) -> str:
    """Process one inbound message and return the reply text to post immediately.

    For a single agent the reply is the answer. For a workflow the reply is an
    acknowledgement — the (possibly slow) workflow runs in the background and its
    final result is delivered back to the channel on completion.
    """
    identity = f"{channel}:{sender_id}"
    async with SessionLocal() as session:
        workflow_id, agent_id = await _resolve_binding(session, channel)

        if workflow_id:
            return await _run_via_workflow(
                session, channel, sender_id, identity, workflow_id, text, thread
            )
        if agent_id:
            return await _run_via_agent(session, channel, identity, agent_id, text)

    return (
        "⚠️ No agent or workflow is connected to this channel yet. "
        "Open the web UI → Channels to bind one."
    )


async def _run_via_workflow(
    session, channel: str, sender_id: str, identity: str, workflow_id: str, text: str,
    thread: str | None,
) -> str:
    workflow = await session.get(Workflow, workflow_id)
    if workflow is None:
        return "⚠️ The connected workflow no longer exists."

    # Record where to deliver the result once the (possibly slow) run finishes.
    origin = {
        "channel": channel,
        "conversation": sender_id,
        "thread": thread,
        "identity": identity,
    }
    run = await run_service.create_run(
        session, workflow_id, text, trigger=channel, origin=origin
    )
    # Record the human turn against the run so it shows in the conversation.
    await message_service.add_message(
        session,
        run_id=run.id,
        role="user",
        sender=identity,
        recipient=workflow.name,
        channel=channel,
        content=text,
    )
    await session.commit()

    # Kick off the workflow in the background; do NOT block the channel handler.
    # The final output is delivered back to this channel on completion.
    run_service.schedule_run(run.id)
    return f"🛠️ Running *{workflow.name}*… I'll post the result here when it's ready."


async def _run_via_agent(
    session, channel: str, identity: str, agent_id: str, text: str
) -> str:
    agent_row = await session.get(Agent, agent_id)
    if agent_row is None:
        return "⚠️ The connected agent no longer exists."
    agent = agent_to_dict(agent_row)

    # Build short conversation history for context/memory.
    history_rows = await message_service.channel_history(session, channel, identity, limit=10)
    history = [
        {"sender": m.sender, "content": m.content, "role": m.role, "node_id": "chat"}
        for m in history_rows
    ]

    # Persist the inbound human turn first.
    await message_service.add_message(
        session,
        role="user",
        sender=identity,
        recipient=agent["name"],
        channel=channel,
        content=text,
    )
    await session.commit()

    bus = get_event_bus()
    await bus.publish(
        Event(type="agent_message", agent_name=identity, data={"content": text, "channel": channel, "inbound": True})
    )

    ctx = RunContext(run_id=None, workflow_id=None)
    reply, usage = await run_single_agent(agent, text, history, ctx)

    await message_service.add_message(
        session,
        role="assistant",
        sender=agent["name"],
        recipient=identity,
        agent_id=agent["id"],
        channel=channel,
        content=reply,
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
    )
    await session.commit()
    return reply
