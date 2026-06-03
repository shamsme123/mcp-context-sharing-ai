"""
app.py — FastAPI application entry point
─────────────────────────────────────────
Architecture:
    Gradio UI → FastAPI (port 8000) → MCP Server → SQLite

Module layout:
    config.py            — env vars & settings
    models.py            — Pydantic request models
    mcp_client.py        — MCP session lifecycle + mcp_call()
    context_routes.py    — /context/* endpoints
    namespace_routes.py  — /namespaces/* endpoints
    chat_routes.py       — /chat endpoints + conversation history
    stats_routes.py      — /stats endpoint

Run:
    python src/server/app.py

Docs:
    http://localhost:8000/docs
"""

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server_config import settings
from mcp_client import lifespan
import context_routes
import namespace_routes
import chat_routes
import stats_routes

# Wire up the histories provider so /stats can report memory turns
stats_routes.set_histories_provider(chat_routes.get_histories)

app = FastAPI(
    title=settings.APP_TITLE,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(context_routes.router)
app.include_router(namespace_routes.router)
app.include_router(chat_routes.router)
app.include_router(stats_routes.router)


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False, app_dir="src")