"""
stats_routes.py — /stats endpoint

Receives a get_histories callable injected by app.py so this module
stays decoupled from chat state.
"""

import json
from typing import Callable

from fastapi import APIRouter

from mcp_client import mcp_call

router = APIRouter(tags=["stats"])

# Injected by app.py after both this module and chat_routes are imported
_get_histories: Callable[[], dict] = lambda: {}


def set_histories_provider(fn: Callable[[], dict]) -> None:
    """Register the callable that returns the live chat histories dict."""
    global _get_histories
    _get_histories = fn


@router.get("/stats", summary="Server health stats")
async def stats():
    result = await mcp_call("server_stats")
    try:
        data = json.loads(result)
    except Exception:
        data = {"raw": result}

    data["memory_turns"] = sum(len(h) for h in _get_histories().values()) // 2
    return data