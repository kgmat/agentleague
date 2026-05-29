"""Message + log-event persistence and queries (the visible history)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import Event
from app.models import LogEvent, Message


async def add_message(session: AsyncSession, **kwargs) -> Message:
    message = Message(**kwargs)
    session.add(message)
    await session.flush()
    return message


async def messages_for_run(session: AsyncSession, run_id: str) -> list[Message]:
    result = await session.execute(
        select(Message).where(Message.run_id == run_id).order_by(Message.created_at)
    )
    return list(result.scalars().all())


async def channel_history(
    session: AsyncSession, channel: str, recipient: str, limit: int = 20
) -> list[Message]:
    """Recent turns for a given channel conversation (e.g. a Telegram chat)."""
    result = await session.execute(
        select(Message)
        .where(Message.channel == channel)
        .where((Message.sender == recipient) | (Message.recipient == recipient))
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    return list(reversed(result.scalars().all()))


async def persist_event(session: AsyncSession, event: Event) -> None:
    session.add(
        LogEvent(
            run_id=event.run_id,
            type=event.type,
            agent_name=event.agent_name,
            data=event.data,
        )
    )
    await session.flush()


async def events_for_run(session: AsyncSession, run_id: str) -> list[LogEvent]:
    result = await session.execute(
        select(LogEvent).where(LogEvent.run_id == run_id).order_by(LogEvent.created_at)
    )
    return list(result.scalars().all())
