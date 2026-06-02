"""
mcp_client.py — MCP session lifecycle and mcp_call() helper

Holds a single long-lived ClientSession created on app startup
and torn down on shutdown via the FastAPI lifespan context manager.
"""

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from config import settings

_mcp_session: Optional[ClientSession] = None
_stdio_ctx   = None
_session_ctx = None


async def mcp_call(tool: str, **kwargs) -> str:
    """Invoke an MCP tool and return the first text result."""
    if _mcp_session is None:
        raise HTTPException(status_code=503, detail="MCP session not ready")
    if settings.MCP_API_KEY:
        kwargs["api_key"] = settings.MCP_API_KEY
    result = await _mcp_session.call_tool(tool, arguments=kwargs)
    return result.content[0].text


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Connect to the MCP server on startup; disconnect on shutdown."""
    global _mcp_session, _stdio_ctx, _session_ctx

    params       = StdioServerParameters(command="python", args=[settings.SERVER_SCRIPT])
    _stdio_ctx   = stdio_client(params)
    read, write  = await _stdio_ctx.__aenter__()
    _session_ctx = ClientSession(read, write)
    _mcp_session = await _session_ctx.__aenter__()
    await _mcp_session.initialize()
    print("MCP server connected")

    yield

    await _session_ctx.__aexit__(None, None, None)
    await _stdio_ctx.__aexit__(None, None, None)
    print("MCP server disconnected")