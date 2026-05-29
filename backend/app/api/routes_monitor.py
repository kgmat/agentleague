"""Live-monitoring WebSockets.

Clients connect and receive a real-time stream of runtime ``Event``s (node
transitions, inter-agent messages, tool calls, token/cost updates, errors).
``/api/ws/monitor`` streams everything; ``/api/ws/runs/{run_id}`` scopes to a run.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.events import GLOBAL_TOPIC, get_event_bus, run_topic
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["monitor"])


async def _stream(websocket: WebSocket, topic: str) -> None:
    await websocket.accept()
    bus = get_event_bus()
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
    await _stream(websocket, run_topic(run_id))
