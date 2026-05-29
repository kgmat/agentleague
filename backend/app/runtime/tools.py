"""Real, executable tools available to agents.

These are genuine tools (network calls, computation, time) — not stubs — so the
runtime "actually executes agent logic". Agents reference tools by name; the
engine binds the corresponding callables to the model for tool-calling.

To add a tool: write a ``@tool`` function and register it in ``TOOL_REGISTRY``.
That single line makes it selectable in the agent editor and bindable at runtime.
"""
from __future__ import annotations

import ast
import datetime as _dt
import operator
from typing import Callable

import httpx
from langchain_core.tools import BaseTool, tool

from app.core.logging import get_logger

logger = get_logger(__name__)


@tool
def web_search(query: str) -> str:
    """Search the web and return the top results as text. Use for current facts."""
    try:
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
        if not results:
            return "No results found."
        lines = [
            f"{i + 1}. {r.get('title', '')}\n   {r.get('body', '')}\n   {r.get('href', '')}"
            for i, r in enumerate(results)
        ]
        return "\n".join(lines)
    except Exception as exc:  # network/ratelimit failures shouldn't crash a run
        logger.warning("web_search failed: %s", exc)
        return f"web_search unavailable ({exc}). Answer from your own knowledge."


@tool
def http_get(url: str) -> str:
    """Fetch the text content of a URL (first 4000 chars). Use to read a page/API."""
    try:
        resp = httpx.get(url, timeout=20, follow_redirects=True)
        resp.raise_for_status()
        text = resp.text
        return text[:4000]
    except Exception as exc:
        return f"Failed to fetch {url}: {exc}"


# Safe arithmetic evaluator — supports + - * / ** % and parentheses only.
_ALLOWED_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
}


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError("Unsupported expression")


@tool
def calculator(expression: str) -> str:
    """Evaluate a math expression, e.g. "12 * (3 + 4) / 2". Safe arithmetic only."""
    try:
        tree = ast.parse(expression, mode="eval")
        return str(_eval_node(tree.body))
    except Exception as exc:
        return f"Could not evaluate {expression!r}: {exc}"


@tool
def current_time() -> str:
    """Return the current UTC date and time in ISO 8601 format."""
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


# name -> tool. The single source of truth for "what tools exist".
TOOL_REGISTRY: dict[str, BaseTool] = {
    "web_search": web_search,
    "http_get": http_get,
    "calculator": calculator,
    "current_time": current_time,
}


def get_tools(names: list[str]) -> list[BaseTool]:
    """Resolve tool names to tool objects, silently skipping unknown names."""
    return [TOOL_REGISTRY[n] for n in names if n in TOOL_REGISTRY]


def get_tool_callable(name: str) -> Callable | None:
    return TOOL_REGISTRY.get(name)


def list_tools() -> list[dict]:
    return [
        {"name": name, "description": (t.description or "").strip()}
        for name, t in TOOL_REGISTRY.items()
    ]
