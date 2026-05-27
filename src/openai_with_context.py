"""
openai_with_context.py — Production version
Pulls context from MCP server and injects into OpenAI calls.
"""

import asyncio
import json
import os
from openai import AsyncOpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv

load_dotenv()

OPENAI_MODEL  = "gpt-4o"
NAMESPACE     = "project-alpha"
SERVER_SCRIPT = "src/server/context_server.py"
API_KEY       = os.getenv("MCP_API_KEY", "")

SERVER_PARAMS = StdioServerParameters(
    command="python",
    args=[SERVER_SCRIPT],
)

openai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


async def mcp_call(session, tool, **kwargs):
    if API_KEY:
        kwargs["api_key"] = API_KEY
    result = await session.call_tool(tool, arguments=kwargs)
    return result.content[0].text


async def build_context_block(session, namespace):
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


async def chat_with_context(session, user_message, namespace):
    context_block = await build_context_block(session, namespace)
    system_prompt = (
        "You are a helpful assistant with access to shared team context.\n\n"
        f"{context_block}\n\nUse this context when answering."
        if context_block else "You are a helpful assistant."
    )
    print(f"\n[Context injected — {len(system_prompt)} chars]\n")

    response = await openai.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
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


async def demo():
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("=== MCP Context Sharing + OpenAI (Production) ===\n")

            print("Storing context...")
            print(await mcp_call(session, "set_context",
                key="project_goal",
                value="Build a multi-agent AI system that shares memory via MCP. Supports namespaces and tag-based filtering.",
                namespace=NAMESPACE, tags="goal,important", ttl_seconds=0,
            ))
            print(await mcp_call(session, "set_context",
                key="tech_stack",
                value="Python 3.12, FastMCP, OpenAI GPT-4o, SQLite, VS Code, asyncio",
                namespace=NAMESPACE, tags="technical",
            ))
            print(await mcp_call(session, "set_context",
                key="team_decision",
                value="stdio transport for dev, SSE transport for production deployment.",
                namespace=NAMESPACE, tags="decision",
            ))

            print("\n--- Server stats ---")
            print(await mcp_call(session, "server_stats"))

            print("\n--- Asking OpenAI ---")
            await chat_with_context(session, "Summarize our project and tech stack.", NAMESPACE)

            print("\n--- Follow-up ---")
            await chat_with_context(session, "What transport decision did the team make and why does it matter?", NAMESPACE)


if __name__ == "__main__":
    asyncio.run(demo())