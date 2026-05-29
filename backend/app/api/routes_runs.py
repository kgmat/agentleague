"""Run inspection endpoints: status, message history, persisted logs."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas import MessageOut, RunDetail, RunOut
from app.services import message_service, run_service

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.get("", response_model=list[RunOut])
async def list_runs(
    workflow_id: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    return await run_service.list_runs(session, workflow_id)


@router.get("/{run_id}", response_model=RunDetail)
async def get_run(run_id: str, session: AsyncSession = Depends(get_session)):
    run = await run_service.get_run(session, run_id)
    if run is None:
        raise HTTPException(404, "Run not found")
    messages = await message_service.messages_for_run(session, run_id)
    # Validate scalar columns via RunOut (avoids touching the lazy ``messages``
    # relationship, which would trigger async IO outside a greenlet context),
    # then attach the explicitly-loaded messages.
    detail = RunDetail(
        **RunOut.model_validate(run).model_dump(),
        messages=[MessageOut.model_validate(m) for m in messages],
    )
    return detail


@router.get("/{run_id}/messages", response_model=list[MessageOut])
async def get_run_messages(run_id: str, session: AsyncSession = Depends(get_session)):
    return await message_service.messages_for_run(session, run_id)


@router.get("/{run_id}/events")
async def get_run_events(run_id: str, session: AsyncSession = Depends(get_session)):
    events = await message_service.events_for_run(session, run_id)
    return [
        {
            "id": e.id,
            "type": e.type,
            "agent_name": e.agent_name,
            "data": e.data,
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]
