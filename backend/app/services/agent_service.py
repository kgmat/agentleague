"""Agent persistence + serialisation helpers."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Agent
from app.schemas import AgentCreate, AgentUpdate


def agent_to_dict(agent: Agent) -> dict:
    """Plain dict the runtime can consume without touching the ORM session."""
    return {
        "id": agent.id,
        "name": agent.name,
        "role": agent.role,
        "system_prompt": agent.system_prompt,
        "provider": agent.provider,
        "model": agent.model,
        "temperature": agent.temperature,
        "tools": agent.tools or [],
        "channels": agent.channels or [],
        "skills": agent.skills or [],
        "memory": agent.memory or {},
        "schedule": agent.schedule or {},
        "interaction_rules": agent.interaction_rules or {},
        "guardrails": agent.guardrails or {},
    }


async def list_agents(session: AsyncSession) -> list[Agent]:
    result = await session.execute(select(Agent).order_by(Agent.created_at.desc()))
    return list(result.scalars().all())


async def get_agent(session: AsyncSession, agent_id: str) -> Agent | None:
    return await session.get(Agent, agent_id)


async def create_agent(session: AsyncSession, data: AgentCreate) -> Agent:
    agent = Agent(
        name=data.name,
        role=data.role,
        system_prompt=data.system_prompt,
        provider=data.provider,
        model=data.model,
        temperature=data.temperature,
        tools=data.tools,
        channels=data.channels,
        skills=data.skills,
        memory=data.memory.model_dump(),
        schedule=data.schedule.model_dump(),
        interaction_rules=data.interaction_rules,
        guardrails=data.guardrails.model_dump(),
    )
    session.add(agent)
    await session.flush()
    await session.refresh(agent)
    return agent


async def update_agent(
    session: AsyncSession, agent: Agent, data: AgentUpdate
) -> Agent:
    # exclude_unset so PATCH semantics hold; model_dump recursively turns the
    # nested config models (memory/schedule/guardrails) into JSON-ready dicts.
    payload = data.model_dump(exclude_unset=True)
    for key, value in payload.items():
        setattr(agent, key, value)
    await session.flush()
    await session.refresh(agent)
    return agent


async def delete_agent(session: AsyncSession, agent: Agent) -> None:
    await session.delete(agent)
    await session.flush()
