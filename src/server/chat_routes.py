"""
chat_routes.py — /chat endpoints + OpenAI integration

Maintains per-namespace conversation history in memory.
"""

import json

from fastapi import APIRouter
from openai import AsyncOpenAI

from server_config import settings
from mcp_client import mcp_call
from models import ChatRequest

router = APIRouter(tags=["chat"])

openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

_histories: dict[str, list[dict]] = {}
MAX_TURNS = 20  # user+assistant pairs kept per namespace


def get_histories() -> dict[str, list[dict]]:
    """Return the live histories dict (consumed by stats_routes)."""
    return _histories


@router.post("/chat", summary="Chat with OpenAI using MCP context")
async def chat(req: ChatRequest):
    # 1. Pull stored context for the namespace
    raw = await mcp_call("list_context", namespace=req.namespace)
    try:
        entries = json.loads(raw)
    except Exception:
        entries = []

    # 2. Build system prompt
    if entries:
        lines = [f"You are a helpful assistant. Shared context from namespace '{req.namespace}':\n"]
        for e in entries:
            val = await mcp_call("get_context", key=e["key"], namespace=req.namespace)
            lines.append(f"[{e['key']}]: {val}")
        system_prompt = "\n".join(lines)
    else:
        system_prompt = "You are a helpful assistant. No context stored yet."

    # 3. Append user message and build full message list
    history = _histories.setdefault(req.namespace, [])
    history.append({"role": "user", "content": req.message})
    messages = [{"role": "system", "content": system_prompt}] + history

    # 4. Call OpenAI
    response = await openai.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=messages,
    )
    reply = response.choices[0].message.content
    history.append({"role": "assistant", "content": reply})

    # Trim old turns
    if len(history) > MAX_TURNS * 2:
        _histories[req.namespace] = history[-(MAX_TURNS * 2):]

    return {
        "reply": reply,
        "namespace": req.namespace,
        "context_keys": [e["key"] for e in entries],
        "memory_turns": len(history) // 2,
    }


@router.post("/chat/reset", summary="Reset conversation history for a namespace")
async def reset_chat(namespace: str = "default"):
    _histories.pop(namespace, None)
    return {"result": f"History cleared for namespace '{namespace}'."}