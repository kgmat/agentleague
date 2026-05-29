"""Outbound channel sender registry.

Channel adapters register a `send(conversation, text, thread)` coroutine here on
startup. The run executor uses it to deliver a workflow's final result back to
the originating channel **after** the run completes — so the channel handler
never blocks on a long workflow (which would risk Slack timeouts / lost replies
across reconnects).

In this single-process design the call is in-memory. If a channel ever moves to
its own worker process, this is the seam that would publish over Redis instead.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.core.logging import get_logger

logger = get_logger(__name__)

# channel name -> async send(conversation_id, text, thread) -> None
Sender = Callable[[str, str, str | None], Awaitable[None]]
_senders: dict[str, Sender] = {}


def register_sender(channel: str, sender: Sender) -> None:
    _senders[channel] = sender
    logger.info("Registered outbound sender for channel '%s'", channel)


def unregister_sender(channel: str) -> None:
    _senders.pop(channel, None)


async def send_to_channel(
    channel: str, conversation: str, text: str, thread: str | None = None
) -> bool:
    """Deliver text to a channel conversation. Returns True if sent."""
    sender = _senders.get(channel)
    if sender is None:
        logger.warning("No outbound sender registered for channel '%s'", channel)
        return False
    try:
        await sender(conversation, text, thread)
        return True
    except Exception as exc:  # noqa: BLE001 - delivery failure must not crash the run
        logger.exception("Failed to deliver to %s/%s: %s", channel, conversation, exc)
        return False
