"""Workflow persistence + template instantiation."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Workflow
from app.schemas import WorkflowCreate, WorkflowUpdate


async def list_workflows(session: AsyncSession) -> list[Workflow]:
    result = await session.execute(select(Workflow).order_by(Workflow.created_at.desc()))
    return list(result.scalars().all())


async def get_workflow(session: AsyncSession, workflow_id: str) -> Workflow | None:
    return await session.get(Workflow, workflow_id)


async def create_workflow(session: AsyncSession, data: WorkflowCreate) -> Workflow:
    workflow = Workflow(
        name=data.name,
        description=data.description,
        graph=data.graph.model_dump(),
    )
    session.add(workflow)
    await session.flush()
    await session.refresh(workflow)
    return workflow


async def update_workflow(
    session: AsyncSession, workflow: Workflow, data: WorkflowUpdate
) -> Workflow:
    payload = data.model_dump(exclude_unset=True)
    for key, value in payload.items():
        setattr(workflow, key, value)
    await session.flush()
    await session.refresh(workflow)
    return workflow


async def delete_workflow(session: AsyncSession, workflow: Workflow) -> None:
    await session.delete(workflow)
    await session.flush()
