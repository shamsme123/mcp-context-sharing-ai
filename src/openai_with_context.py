"""
openai_with_context.py
────────────────────────────────────────────────────────────────
Connects to the MCP Context Server via stdio, pulls context from
a namespace, injects it into an OpenAI chat prompt, and streams
the response back.

Usage:
    python src/openai_with_context.py

Requirements:
    pip install mcp[cli] openai python-dotenv
"""

import asyncio
import os
from openai import AsyncOpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv

load_dotenv()

# ── Config ─────────────────────────────────────────────────────
OPENAI_MODEL   = "gpt-4o"
NAMESPACE      = "project-alpha"          # which namespace to pull context from
SERVER_SCRIPT  = "src/server/context_server.py"

SERVER_PARAMS = StdioServerParameters(
    command="python",
    args=[SERVER_SCRIPT],
)

openai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ── Helpers ────────────────────────────────────────────────────

async def mcp_call(session: ClientSession, tool: str, **kwargs) -> str:
    result = await session.call_tool(tool, arguments=kwargs)
    return result.content[0].text


async def build_context_block(session: ClientSession, namespace: str) -> str:
    """Fetch all entries from a namespace and format them as a context block."""
    raw = await mcp_call(session, "list_context", namespace=namespace)
    if raw.startswith("No entries"):
        return ""

    import json
    try:
        entries = json.loads(raw)
    except Exception:
        return raw

    lines = [f"## Context from namespace '{namespace}'"]
    for entry in entries:
        lines.append(f"\n### {entry['key']}")
        # Fetch full value (preview may be truncated)
        full_value = await mcp_call(session, "get_context", key=entry["key"], namespace=namespace)
        lines.append(full_value)

    return "\n".join(lines)


async def chat_with_context(session: ClientSession, user_message: str, namespace: str) -> str:
    """
    1. Pull all context from the MCP server for the given namespace.
    2. Inject it as a system message into the OpenAI call.
    3. Return the assistant's reply.
    """
    context_block = await build_context_block(session, namespace)

    system_prompt = (
        "You are a helpful assistant. "
        "You have access to the following shared context from your team:\n\n"
        f"{context_block}\n\n"
        "Use this context when answering. "
        "If the context doesn't contain enough information, say so clearly."
    ) if context_block else "You are a helpful assistant."

    print(f"\n[System prompt built — {len(system_prompt)} chars of context injected]\n")

    response = await openai.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ],
        stream=True,
    )

    full_reply = ""
    async for chunk in response:
        delta = chunk.choices[0].delta.content or ""
        print(delta, end="", flush=True)
        full_reply += delta

    print()  # newline after streaming
    return full_reply


# ── Demo ───────────────────────────────────────────────────────

async def demo():
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            print("=== MCP Context Sharing + OpenAI Demo ===\n")

            # 1. Store some context via MCP tools
            print("Storing context...")
            print(await mcp_call(session, "set_context",
                key="project_goal",
                value="Build a multi-agent AI system that shares memory using MCP. "
                      "The system must support multiple namespaces and tag-based filtering.",
                namespace=NAMESPACE,
                tags="goal,important",
            ))
            print(await mcp_call(session, "set_context",
                key="tech_stack",
                value="Python 3.12, FastMCP, OpenAI GPT-4o, VS Code, asyncio",
                namespace=NAMESPACE,
                tags="technical",
            ))
            print(await mcp_call(session, "set_context",
                key="team_decision",
                value="Decided to use stdio transport for local development "
                      "and SSE transport for production deployment.",
                namespace=NAMESPACE,
                tags="decision",
            ))

            # 2. Chat using that context
            print("\n--- Asking OpenAI with injected context ---")
            await chat_with_context(
                session,
                user_message="Summarize our project and explain the tech stack we chose.",
                namespace=NAMESPACE,
            )

            # 3. Ask something that requires specific context
            print("\n--- Follow-up question ---")
            await chat_with_context(
                session,
                user_message="What transport decision did our team make and why might that matter?",
                namespace=NAMESPACE,
            )


if __name__ == "__main__":
    asyncio.run(demo())