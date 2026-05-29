"""Agent CRUD endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas import AgentCreate, AgentOut, AgentUpdate
from app.services import agent_service

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("", response_model=list[AgentOut])
async def list_agents(session: AsyncSession = Depends(get_session)):
    return await agent_service.list_agents(session)


@router.post("", response_model=AgentOut, status_code=201)
async def create_agent(data: AgentCreate, session: AsyncSession = Depends(get_session)):
    return await agent_service.create_agent(session, data)


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(agent_id: str, session: AsyncSession = Depends(get_session)):
    agent = await agent_service.get_agent(session, agent_id)
    if agent is None:
        raise HTTPException(404, "Agent not found")
    return agent


@router.put("/{agent_id}", response_model=AgentOut)
async def update_agent(
    agent_id: str, data: AgentUpdate, session: AsyncSession = Depends(get_session)
):
    agent = await agent_service.get_agent(session, agent_id)
    if agent is None:
        raise HTTPException(404, "Agent not found")
    return await agent_service.update_agent(session, agent, data)


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(agent_id: str, session: AsyncSession = Depends(get_session)):
    agent = await agent_service.get_agent(session, agent_id)
    if agent is None:
        raise HTTPException(404, "Agent not found")
    await agent_service.delete_agent(session, agent)
