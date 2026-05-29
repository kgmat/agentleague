"""Critical path: agent creation (and the rest of CRUD)."""
from __future__ import annotations

from app.schemas import AgentCreate, AgentUpdate, Guardrails
from app.services import agent_service


async def test_create_and_fetch_agent(session):
    created = await agent_service.create_agent(
        session,
        AgentCreate(
            name="Researcher",
            role="research analyst",
            system_prompt="Find facts.",
            tools=["web_search"],
            guardrails=Guardrails(max_steps=4, blocked_words=["secret"]),
        ),
    )
    assert created.id
    assert created.name == "Researcher"
    assert created.tools == ["web_search"]
    assert created.guardrails["max_steps"] == 4

    fetched = await agent_service.get_agent(session, created.id)
    assert fetched is not None
    assert fetched.id == created.id


async def test_update_and_delete_agent(session):
    agent = await agent_service.create_agent(session, AgentCreate(name="Temp"))
    updated = await agent_service.update_agent(
        session, agent, AgentUpdate(name="Renamed", temperature=0.2)
    )
    assert updated.name == "Renamed"
    assert updated.temperature == 0.2

    await agent_service.delete_agent(session, updated)
    assert await agent_service.get_agent(session, agent.id) is None


async def test_agent_serialises_to_runtime_dict(session):
    agent = await agent_service.create_agent(
        session, AgentCreate(name="A", tools=["calculator"], model="qwen2.5")
    )
    as_dict = agent_service.agent_to_dict(agent)
    assert as_dict["name"] == "A"
    assert as_dict["tools"] == ["calculator"]
    assert "guardrails" in as_dict and "memory" in as_dict
