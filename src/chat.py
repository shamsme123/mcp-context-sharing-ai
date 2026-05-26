"""
chat.py  —  Interactive multi-turn chat with MCP context + OpenAI
────────────────────────────────────────────────────────────────────
Commands during chat:
  /set  <key> <value>     — store context
  /get  <key>             — retrieve context
  /list                   — list all context in current namespace
  /ns   <name>            — switch namespace
  /help                   — show commands
  /quit                   — exit

Usage:
    python src/chat.py
"""

import asyncio
import os
import json
from openai import AsyncOpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv

load_dotenv()

SERVER_PARAMS = StdioServerParameters(
    command="python",
    args=["src/server/context_server.py"],
)

openai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
OPENAI_MODEL = "gpt-4o"


async def mcp_call(session, tool, **kwargs):
    result = await session.call_tool(tool, arguments=kwargs)
    return result.content[0].text


async def get_context_system_prompt(session, namespace):
    raw = await mcp_call(session, "list_context", namespace=namespace)
    if raw.startswith("No entries"):
        return "You are a helpful assistant. No context has been stored yet."

    try:
        entries = json.loads(raw)
    except Exception:
        return "You are a helpful assistant."

    lines = [f"You are a helpful assistant. Use this shared context:\n"]
    for e in entries:
        full = await mcp_call(session, "get_context", key=e["key"], namespace=namespace)
        lines.append(f"[{e['key']}]: {full}")

    return "\n".join(lines)


async def handle_command(session, cmd, namespace):
    """Handle /commands. Returns (output_string, new_namespace)."""
    parts = cmd.strip().split(" ", 2)
    verb = parts[0].lower()

    if verb == "/help":
        return (
            "Commands:\n"
            "  /set <key> <value>  — store context\n"
            "  /get <key>          — retrieve context\n"
            "  /list               — list all context\n"
            "  /ns <name>          — switch namespace\n"
            "  /quit               — exit\n"
        ), namespace

    if verb == "/set" and len(parts) >= 3:
        key, value = parts[1], parts[2]
        msg = await mcp_call(session, "set_context", key=key, value=value, namespace=namespace)
        return msg, namespace

    if verb == "/get" and len(parts) >= 2:
        value = await mcp_call(session, "get_context", key=parts[1], namespace=namespace)
        return f"[{parts[1]}]: {value}", namespace

    if verb == "/list":
        result = await mcp_call(session, "list_context", namespace=namespace)
        return result, namespace

    if verb == "/ns" and len(parts) >= 2:
        new_ns = parts[1]
        return f"Switched to namespace '{new_ns}'.", new_ns

    return f"Unknown command '{verb}'. Type /help for help.", namespace


async def main():
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            namespace = "default"
            history = []

            print("MCP Context Chat  (OpenAI + MCP)")
            print(f"Namespace: '{namespace}'  |  Type /help for commands\n")

            while True:
                try:
                    user_input = input("You: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\nGoodbye.")
                    break

                if not user_input:
                    continue

                if user_input.lower() in ("/quit", "/exit"):
                    print("Goodbye.")
                    break

                # Handle slash commands
                if user_input.startswith("/"):
                    output, namespace = await handle_command(session, user_input, namespace)
                    print(f"[{namespace}] {output}\n")
                    continue

                # Normal chat — inject MCP context as system prompt
                system = await get_context_system_prompt(session, namespace)
                history.append({"role": "user", "content": user_input})

                messages = [{"role": "system", "content": system}] + history

                print("Assistant: ", end="", flush=True)
                reply = ""
                response = await openai.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=messages,
                    stream=True,
                )
                async for chunk in response:
                    delta = chunk.choices[0].delta.content or ""
                    print(delta, end="", flush=True)
                    reply += delta

                print("\n")
                history.append({"role": "assistant", "content": reply})

                # Keep history to last 20 turns
                if len(history) > 40:
                    history = history[-40:]


if __name__ == "__main__":
    asyncio.run(main())