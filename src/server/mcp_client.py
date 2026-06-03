import sys
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from server_config import settings

_mcp_session: Optional[ClientSession] = None
_stdio_ctx   = None
_session_ctx = None


async def mcp_call(tool: str, **kwargs) -> str:
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

    # 🌟 FIX: Find 'src/mcp' directory dynamically and add it to the python execution search path
    mcp_dir = os.path.dirname(settings.SERVER_SCRIPT)
    custom_env = os.environ.copy()
    custom_env["PYTHONPATH"] = f"{mcp_dir};{custom_env.get('PYTHONPATH', '')}"

    # Use sys.executable instead of a loose "python" string to stay within your env boundary on Windows
    params = StdioServerParameters(
        command=sys.executable, 
        args=[settings.SERVER_SCRIPT],
        env=custom_env
    )
    
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