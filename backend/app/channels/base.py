"""Channel abstraction.

A messaging channel is anything that can (a) receive inbound human messages and
(b) deliver outbound agent replies. Keeping this interface small is what makes
"add a new messaging channel" a contained task: implement ``start``/``stop`` and
forward inbound text to the shared :func:`app.channels.router.handle_inbound`.
(See README → "Adding a messaging channel".)
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class Channel(ABC):
    name: str = "base"

    @abstractmethod
    async def start(self) -> None:
        """Begin receiving messages (e.g. start polling / open a socket)."""

    @abstractmethod
    async def stop(self) -> None:
        """Gracefully stop receiving messages."""

    @property
    def running(self) -> bool:
        return False
