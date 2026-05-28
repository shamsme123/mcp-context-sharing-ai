"""
api.py — FastAPI server that wraps the MCP Context Server
──────────────────────────────────────────────────────────
Architecture:
    Gradio UI → FastAPI (port 8000) → MCP Server → SQLite

Run:
    python src/api.py

Docs:
    http://localhost:8000/docs
"""

import json
import os
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import BaseModel

from dotenv import load_dotenv
from pathlib import Path

# Always load .env from project root regardless of where script is run from
load_dotenv(Path(__file__).parent.parent / ".env")

MCP_API_KEY   = os.getenv("MCP_API_KEY", "")
OPENAI_MODEL  = os.getenv("OPENAI_MODEL", "gpt-4o")
SERVER_SCRIPT = "src/server/context_server.py"

openai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ── Global MCP session ────────────────────────────────────────────────────────
_mcp_session: Optional[ClientSession] = None
_stdio_ctx   = None
_session_ctx = None

# Simple in-memory conversation history per namespace
_histories: dict[str, list[dict]] = {}


async def mcp_call(tool: str, **kwargs) -> str:
    if _mcp_session is None:
        raise HTTPException(status_code=503, detail="MCP session not ready")
    if MCP_API_KEY:
        kwargs["api_key"] = MCP_API_KEY
    result = await _mcp_session.call_tool(tool, arguments=kwargs)
    return result.content[0].text


# ── Lifespan: connect MCP on startup, disconnect on shutdown ──────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _mcp_session, _stdio_ctx, _session_ctx

    params = StdioServerParameters(command="python", args=[SERVER_SCRIPT])
    _stdio_ctx          = stdio_client(params)
    read, write         = await _stdio_ctx.__aenter__()
    _session_ctx        = ClientSession(read, write)
    _mcp_session        = await _session_ctx.__aenter__()
    await _mcp_session.initialize()
    print("✅ MCP server connected")

    yield

    await _session_ctx.__aexit__(None, None, None)
    await _stdio_ctx.__aexit__(None, None, None)
    print("MCP server disconnected")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="MCP Context Sharing API",
    description="REST API wrapping the MCP Context Server. Consumed by the Gradio UI.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic models ───────────────────────────────────────────────────────────
class SetContextRequest(BaseModel):
    namespace:   str = "default"
    key:         str
    value:       str
    tags:        str = ""
    ttl_seconds: int = 0


class ShareContextRequest(BaseModel):
    key:              str
    source_namespace: str
    target_namespace: str
    new_key:          Optional[str] = None


class ChatRequest(BaseModel):
    message:   str
    namespace: str = "default"


# ── Context endpoints ─────────────────────────────────────────────────────────
@app.post("/context/set", summary="Store a context entry")
async def set_context(req: SetContextRequest):
    result = await mcp_call(
        "set_context",
        key=req.key, value=req.value,
        namespace=req.namespace, tags=req.tags,
        ttl_seconds=req.ttl_seconds,
    )
    return {"result": result}


@app.get("/context/get/{namespace}/{key}", summary="Retrieve a context entry")
async def get_context(namespace: str, key: str):
    result = await mcp_call("get_context", key=key, namespace=namespace)
    if "not found" in result:
        raise HTTPException(status_code=404, detail=result)
    return {"key": key, "namespace": namespace, "value": result}


@app.get("/context/list/{namespace}", summary="List all entries in a namespace")
async def list_context(namespace: str, tag_filter: str = Query(default="")):
    result = await mcp_call("list_context", namespace=namespace, tag_filter=tag_filter)
    try:
        return {"namespace": namespace, "entries": json.loads(result)}
    except Exception:
        return {"namespace": namespace, "entries": [], "message": result}


@app.delete("/context/delete/{namespace}/{key}", summary="Delete a context entry")
async def delete_context(namespace: str, key: str):
    result = await mcp_call("delete_context", key=key, namespace=namespace)
    return {"result": result}


@app.get("/context/search/{namespace}", summary="Search context entries")
async def search_context(namespace: str, query: str = Query(...)):
    result = await mcp_call("search_context", query=query, namespace=namespace)
    try:
        return {"namespace": namespace, "matches": json.loads(result)}
    except Exception:
        return {"namespace": namespace, "matches": [], "message": result}


@app.post("/context/share", summary="Share a context entry between namespaces")
async def share_context(req: ShareContextRequest):
    result = await mcp_call(
        "share_context",
        key=req.key,
        source_namespace=req.source_namespace,
        target_namespace=req.target_namespace,
        new_key=req.new_key,
    )
    return {"result": result}


# ── Namespace endpoints ───────────────────────────────────────────────────────
@app.get("/namespaces", summary="List all namespaces")
async def list_namespaces():
    result = await mcp_call("list_namespaces")
    try:
        return {"namespaces": json.loads(result)}
    except Exception:
        return {"namespaces": {}, "message": result}


@app.delete("/namespaces/{namespace}", summary="Clear all entries in a namespace")
async def clear_namespace(namespace: str):
    result = await mcp_call("clear_namespace", namespace=namespace)
    return {"result": result}


# ── Stats endpoint ────────────────────────────────────────────────────────────
@app.get("/stats", summary="Server health stats")
async def stats():
    result = await mcp_call("server_stats")
    try:
        data = json.loads(result)
        data["memory_turns"] = sum(len(h) for h in _histories.values()) // 2
        return data
    except Exception:
        return {"raw": result}


# ── Chat endpoint (OpenAI only) ───────────────────────────────────────────────
@app.post("/chat", summary="Chat with OpenAI using MCP context")
async def chat(req: ChatRequest):
    # 1. Pull context from MCP server
    raw = await mcp_call("list_context", namespace=req.namespace)
    try:
        entries = json.loads(raw)
    except Exception:
        entries = []

    # 2. Build system prompt from context
    if entries:
        lines = [f"You are a helpful assistant. Shared context from namespace '{req.namespace}':\n"]
        for e in entries:
            val = await mcp_call("get_context", key=e["key"], namespace=req.namespace)
            lines.append(f"[{e['key']}]: {val}")
        system_prompt = "\n".join(lines)
    else:
        system_prompt = "You are a helpful assistant. No context stored yet."

    # 3. Maintain per-namespace history
    history = _histories.setdefault(req.namespace, [])
    history.append({"role": "user", "content": req.message})

    messages = [{"role": "system", "content": system_prompt}] + history

    # 4. Call OpenAI
    response = await openai.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
    )
    reply = response.choices[0].message.content
    history.append({"role": "assistant", "content": reply})

    # Keep last 20 turns
    if len(history) > 40:
        _histories[req.namespace] = history[-40:]

    return {
        "reply": reply,
        "namespace": req.namespace,
        "context_keys": [e["key"] for e in entries],
        "memory_turns": len(history) // 2,
    }


@app.post("/chat/reset", summary="Reset conversation history")
async def reset_chat(namespace: str = "default"):
    _histories.pop(namespace, None)
    return {"result": f"History cleared for namespace '{namespace}'."}


# ── Launch ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False, app_dir="src")
