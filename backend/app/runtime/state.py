"""Shared graph state for a workflow run.

LangGraph threads a single ``GraphState`` dict through every node. We use an
additive reducer for the running transcript so each agent node simply *returns*
the new turns it produced and LangGraph concatenates them.
"""
from __future__ import annotations

import operator
from typing import Annotated, TypedDict


class Turn(TypedDict):
    """One entry in the shared, cross-agent conversation transcript."""

    sender: str
    node_id: str
    content: str
    role: str


class GraphState(TypedDict, total=False):
    input: str                                   # the human task that kicked off the run
    transcript: Annotated[list[Turn], operator.add]  # additive across nodes
    last_output: str                             # latest agent output (for edge conditions)
    last_node: str
    visits: dict[str, int]                       # node_id -> times executed (loop guard)
    steps: int                                   # total node executions (global guard)
