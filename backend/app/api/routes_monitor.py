"""Live-monitoring WebSockets.

Clients connect and receive a real-time stream of runtime ``Event``s (node
transitions, inter-agent messages, tool calls, token/cost updates, errors).
``/api/ws/monitor`` streams everything; ``/api/ws/runs/{run_id}`` scopes to a run.
"""
from __future__ import annotations

import asyncio
import json
from datetime import timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.database import SessionLocal
from app.core.events import GLOBAL_TOPIC, get_event_bus, run_topic
from app.core.logging import get_logger
from app.services import message_service

logger = get_logger(__name__)
router = APIRouter(tags=["monitor"])


async def _send_history(websocket: WebSocket, run_id: str | None) -> None:
    """Replay persisted events on connect so late joiners see the full sequence."""
    try:
        async with SessionLocal() as session:
            events = (
                await message_service.events_for_run(session, run_id)
                if run_id
                else await message_service.recent_events(session, 150)
            )
        for e in events:
            # SQLite returns naive datetimes; treat them as UTC so the epoch
            # (and the UI's local-time display) is correct rather than tz-skewed.
            created = e.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            await websocket.send_text(
                json.dumps(
                    {
                        "type": e.type,
                        "run_id": e.run_id,
                        "workflow_id": None,
                        "agent_id": None,
                        "agent_name": e.agent_name,
                        "data": e.data,
                        "ts": created.timestamp(),
                        "replay": True,
                    }
                )
            )
    except Exception as exc:  # noqa: BLE001 - history is best-effort
        logger.debug("history replay failed: %s", exc)


async def _stream(websocket: WebSocket, topic: str, run_id: str | None = None) -> None:
    await websocket.accept()
    bus = get_event_bus()
    await _send_history(websocket, run_id)
    producer = bus.subscribe(topic)

    async def pump() -> None:
        async for event in producer:
            await websocket.send_text(event.to_json())

    pump_task = asyncio.create_task(pump())
    try:
        # Keep the socket alive; we don't expect inbound messages but draining
        # them lets us detect disconnects promptly.
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.debug("monitor socket closed: %s", exc)
    finally:
        pump_task.cancel()


@router.websocket("/api/ws/monitor")
async def monitor_all(websocket: WebSocket):
    await _stream(websocket, GLOBAL_TOPIC)


@router.websocket("/api/ws/runs/{run_id}")
async def monitor_run(websocket: WebSocket, run_id: str):
    await _stream(websocket, run_topic(run_id), run_id)
