"""Run orchestration: create runs, execute them in the background, finalise.

This is the seam between the API layer and the agent runtime. The HTTP request
only *creates* a run row and schedules execution; the actual graph runs in a
background task with its own DB session so the request returns immediately and
the UI can follow progress over the monitoring WebSocket.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.core.events import Event
from app.core.logging import get_logger
from app.models import Agent, Workflow, WorkflowRun
from app.runtime.engine import RunContext, execute_workflow
from app.runtime.providers import Usage
from app.services import message_service
from app.services.agent_service import agent_to_dict

logger = get_logger(__name__)


async def create_run(
    session: AsyncSession, workflow_id: str, user_input: str, trigger: str = "manual"
) -> WorkflowRun:
    run = WorkflowRun(
        workflow_id=workflow_id,
        status="pending",
        trigger=trigger,
        input={"text": user_input},
    )
    session.add(run)
    await session.flush()
    await session.refresh(run)
    return run


async def get_run(session: AsyncSession, run_id: str) -> WorkflowRun | None:
    return await session.get(WorkflowRun, run_id)


async def list_runs(
    session: AsyncSession, workflow_id: str | None = None, limit: int = 50
) -> list[WorkflowRun]:
    stmt = select(WorkflowRun).order_by(WorkflowRun.started_at.desc()).limit(limit)
    if workflow_id:
        stmt = stmt.where(WorkflowRun.workflow_id == workflow_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


def schedule_run(run_id: str) -> None:
    """Fire-and-forget background execution of a run."""
    asyncio.create_task(_execute(run_id))


async def _execute(run_id: str) -> None:
    """Background entrypoint: load everything, run the graph, persist results."""
    async with SessionLocal() as session:
        run = await session.get(WorkflowRun, run_id)
        if run is None:
            logger.error("Run %s vanished before execution", run_id)
            return
        workflow = await session.get(Workflow, run.workflow_id)
        if workflow is None:
            run.status = "failed"
            run.error = "Workflow not found"
            run.finished_at = datetime.now(timezone.utc)
            await session.commit()
            return

        agents = {a.id: agent_to_dict(a) for a in await _all_agents(session)}

        # Callbacks wire the runtime back into persistence + the run's counters.
        async def on_event(event: Event) -> None:
            await message_service.persist_event(session, event)
            await session.commit()

        async def on_message(**kwargs) -> None:
            await message_service.add_message(session, run_id=run_id, **kwargs)
            await session.commit()

        async def on_usage(usage: Usage, cost: float) -> None:
            run.prompt_tokens += usage.prompt_tokens
            run.completion_tokens += usage.completion_tokens
            run.total_tokens += usage.total_tokens
            run.cost_usd = round(run.cost_usd + cost, 6)
            await session.commit()

        ctx = RunContext(
            run_id=run_id,
            workflow_id=workflow.id,
            on_event=on_event,
            on_message=on_message,
            on_usage=on_usage,
        )

        run.status = "running"
        await session.commit()
        await ctx.emit("run_status", data={"status": "running"})

        try:
            final_state = await execute_workflow(
                workflow.graph, agents, run.input.get("text", ""), ctx
            )
            run.status = "completed"
            run.output = {
                "text": final_state.get("last_output", ""),
                "last_node": final_state.get("last_node", ""),
            }
            run.step_count = final_state.get("steps", 0)
        except Exception as exc:  # noqa: BLE001 - surface any failure on the run
            logger.exception("Run %s failed", run_id)
            run.status = "failed"
            run.error = str(exc)
            await ctx.emit("error", data={"message": str(exc)})
        finally:
            run.finished_at = datetime.now(timezone.utc)
            await session.commit()
            await ctx.emit(
                "run_status",
                data={
                    "status": run.status,
                    "total_tokens": run.total_tokens,
                    "cost_usd": run.cost_usd,
                },
            )


async def _all_agents(session: AsyncSession) -> list[Agent]:
    result = await session.execute(select(Agent))
    return list(result.scalars().all())
