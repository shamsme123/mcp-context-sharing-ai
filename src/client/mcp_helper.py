"""
mcp_helper.py — Shared MCP utilities used by chat.py and demo.py

Provides:
    mcp_call()              — invoke any MCP tool
    get_system_prompt()     — context as a flat system prompt (used by chat)
    build_context_block()   — context as a rich markdown block (used by demo)
"""

import json
from mcp import ClientSession, StdioServerParameters

from client_config import settings


SERVER_PARAMS = StdioServerParameters(
    command="python",
    args=[settings.SERVER_SCRIPT],
)


async def mcp_call(session: ClientSession, tool: str, **kwargs) -> str:
    """Invoke an MCP tool and return the first text result."""
    if settings.MCP_API_KEY:
        kwargs["api_key"] = settings.MCP_API_KEY
    result = await session.call_tool(tool, arguments=kwargs)
    return result.content[0].text


async def get_system_prompt(session: ClientSession, namespace: str) -> str:
    """Build a flat system prompt from all context entries in a namespace.

    Used by the interactive chat client.
    """
    raw = await mcp_call(session, "list_context", namespace=namespace)
    if raw.startswith("No entries") or raw.startswith("Error"):
        return "You are a helpful assistant. No context stored yet."
    try:
        entries = json.loads(raw)
    except Exception:
        return "You are a helpful assistant."

    lines = ["You are a helpful assistant. Use this shared context:\n"]
    for e in entries:
        full = await mcp_call(session, "get_context", key=e["key"], namespace=namespace)
        lines.append(f"[{e['key']}]: {full}")
    return "\n".join(lines)


async def build_context_block(session: ClientSession, namespace: str) -> str:
    """Build a rich markdown context block from all entries in a namespace.

    Used by the demo client.
    """
    raw = await mcp_call(session, "list_context", namespace=namespace)
    if raw.startswith("No entries") or raw.startswith("Error"):
        return ""
    try:
        entries = json.loads(raw)
    except Exception:
        return raw

    lines = [f"## Shared context — namespace '{namespace}'"]
    for entry in entries:
        full = await mcp_call(session, "get_context", key=entry["key"], namespace=namespace)
        lines.append(f"\n### {entry['key']}\n{full}")
    return "\n".join(lines)