"""
demo.py — Demonstrates MCP context injection into OpenAI calls

Stores a few context entries, then asks OpenAI questions that
require that context to answer correctly.

Run:
    python src/client/demo.py
"""

import asyncio

from openai import AsyncOpenAI
from mcp.client.stdio import stdio_client
from mcp import ClientSession

from client_config import settings
from mcp_helper import SERVER_PARAMS, mcp_call, build_context_block

openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


async def chat_with_context(session: ClientSession, user_message: str, namespace: str) -> str:
    """Inject namespace context into a single OpenAI completion."""
    context_block = await build_context_block(session, namespace)

    if context_block:
        system_prompt = (
            "You are a helpful assistant with access to shared team context.\n\n"
            f"{context_block}\n\nUse this context when answering."
        )
    else:
        system_prompt = "You are a helpful assistant."

    print(f"\n[Context injected — {len(system_prompt)} chars]\n")

    response = await openai.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system",  "content": system_prompt},
            {"role": "user",    "content": user_message},
        ],
        stream=True,
    )
    full = ""
    async for chunk in response:
        delta = chunk.choices[0].delta.content or ""
        print(delta, end="", flush=True)
        full += delta
    print()
    return full


async def demo() -> None:
    namespace = settings.DEMO_NAMESPACE

    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("=== MCP Context Sharing + OpenAI Demo ===\n")

            # ── Seed context ──────────────────────────────────────────────────
            print("Storing context...")
            print(await mcp_call(session, "set_context",
                key="project_goal",
                value=(
                    "Build a multi-agent AI system that shares memory via MCP. "
                    "Supports namespaces and tag-based filtering."
                ),
                namespace=namespace, tags="goal,important", ttl_seconds=0,
            ))
            print(await mcp_call(session, "set_context",
                key="tech_stack",
                value="Python 3.12, FastMCP, OpenAI GPT-4o, SQLite, VS Code, asyncio",
                namespace=namespace, tags="technical",
            ))
            print(await mcp_call(session, "set_context",
                key="team_decision",
                value="stdio transport for dev, SSE transport for production deployment.",
                namespace=namespace, tags="decision",
            ))

            # ── Server stats ──────────────────────────────────────────────────
            print("\n--- Server stats ---")
            print(await mcp_call(session, "server_stats"))

            # ── Demo queries ──────────────────────────────────────────────────
            print("\n--- Asking OpenAI ---")
            await chat_with_context(
                session,
                "Summarize our project and tech stack.",
                namespace,
            )

            print("\n--- Follow-up ---")
            await chat_with_context(
                session,
                "What transport decision did the team make and why does it matter?",
                namespace,
            )


if __name__ == "__main__":
    asyncio.run(demo())