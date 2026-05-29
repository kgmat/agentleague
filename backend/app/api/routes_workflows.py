"""Workflow CRUD + run-triggering endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas import (
    RunCreate,
    RunOut,
    WorkflowCreate,
    WorkflowOut,
    WorkflowUpdate,
)
from app.services import run_service, workflow_service

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


@router.get("", response_model=list[WorkflowOut])
async def list_workflows(session: AsyncSession = Depends(get_session)):
    return await workflow_service.list_workflows(session)


@router.post("", response_model=WorkflowOut, status_code=201)
async def create_workflow(data: WorkflowCreate, session: AsyncSession = Depends(get_session)):
    return await workflow_service.create_workflow(session, data)


@router.get("/{workflow_id}", response_model=WorkflowOut)
async def get_workflow(workflow_id: str, session: AsyncSession = Depends(get_session)):
    wf = await workflow_service.get_workflow(session, workflow_id)
    if wf is None:
        raise HTTPException(404, "Workflow not found")
    return wf


@router.put("/{workflow_id}", response_model=WorkflowOut)
async def update_workflow(
    workflow_id: str, data: WorkflowUpdate, session: AsyncSession = Depends(get_session)
):
    wf = await workflow_service.get_workflow(session, workflow_id)
    if wf is None:
        raise HTTPException(404, "Workflow not found")
    return await workflow_service.update_workflow(session, wf, data)


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(workflow_id: str, session: AsyncSession = Depends(get_session)):
    wf = await workflow_service.get_workflow(session, workflow_id)
    if wf is None:
        raise HTTPException(404, "Workflow not found")
    await workflow_service.delete_workflow(session, wf)


@router.post("/{workflow_id}/run", response_model=RunOut, status_code=202)
async def run_workflow(
    workflow_id: str, data: RunCreate, session: AsyncSession = Depends(get_session)
):
    """Create a run and execute it in the background. Returns immediately."""
    wf = await workflow_service.get_workflow(session, workflow_id)
    if wf is None:
        raise HTTPException(404, "Workflow not found")
    run = await run_service.create_run(session, workflow_id, data.input, data.trigger)
    await session.commit()  # ensure the run row is visible to the background task
    run_service.schedule_run(run.id)
    return run
