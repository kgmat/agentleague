"""Regression: run-detail serialisation must not lazy-load the ORM relationship.

Reproduces the MissingGreenlet error that occurred when ``RunDetail`` was built
via ``model_validate`` directly on the ORM object (which touched the lazy
``messages`` relationship). The endpoint now validates scalars then attaches
explicitly-loaded messages.
"""
from __future__ import annotations

from app.api.routes_runs import get_run
from app.models import Message, Workflow, WorkflowRun


async def test_run_detail_serializes_with_messages(session):
    wf = Workflow(name="w", graph={"nodes": [], "edges": []})
    session.add(wf)
    await session.flush()

    run = WorkflowRun(
        workflow_id=wf.id, status="completed",
        input={"text": "hi"}, output={"text": "bye"}, total_tokens=5,
    )
    session.add(run)
    await session.flush()

    session.add(Message(run_id=run.id, role="assistant", sender="A", content="hello"))
    await session.flush()

    detail = await get_run(run.id, session)
    assert detail.id == run.id
    assert detail.output["text"] == "bye"
    assert len(detail.messages) == 1
    assert detail.messages[0].content == "hello"
