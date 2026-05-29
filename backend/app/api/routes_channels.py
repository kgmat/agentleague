"""Channel binding management + channel status."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.channels.slack import slack_status
from app.channels.telegram import telegram_status
from app.core.database import get_session
from app.models import ChannelBinding
from app.schemas import ChannelBindingCreate, ChannelBindingOut

router = APIRouter(prefix="/api/channels", tags=["channels"])


@router.get("/status")
async def status():
    return {"telegram": telegram_status(), "slack": slack_status()}


@router.get("/bindings", response_model=list[ChannelBindingOut])
async def list_bindings(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(ChannelBinding).order_by(ChannelBinding.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/bindings", response_model=ChannelBindingOut, status_code=201)
async def create_binding(
    data: ChannelBindingCreate, session: AsyncSession = Depends(get_session)
):
    if not data.agent_id and not data.workflow_id:
        raise HTTPException(400, "Provide either agent_id or workflow_id")
    binding = ChannelBinding(**data.model_dump())
    session.add(binding)
    await session.flush()
    await session.refresh(binding)
    return binding


@router.delete("/bindings/{binding_id}", status_code=204)
async def delete_binding(binding_id: str, session: AsyncSession = Depends(get_session)):
    binding = await session.get(ChannelBinding, binding_id)
    if binding is None:
        raise HTTPException(404, "Binding not found")
    await session.delete(binding)
