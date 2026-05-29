"""Template listing + instantiation."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas import TemplateOut, WorkflowOut
from app.templates import builtin

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("", response_model=list[TemplateOut])
async def list_templates():
    return builtin.list_templates()


@router.post("/{key}/instantiate", response_model=WorkflowOut, status_code=201)
async def instantiate_template(key: str, session: AsyncSession = Depends(get_session)):
    try:
        return await builtin.instantiate(session, key)
    except KeyError:
        raise HTTPException(404, f"Unknown template: {key}")
