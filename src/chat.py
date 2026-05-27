"""
chat.py — Production interactive chat with MCP context + OpenAI
Commands: /set /get /list /ns /stats /expire /search /quit
"""

import asyncio
import json
import os
from openai import AsyncOpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv

load_dotenv()

SERVER_PARAMS = StdioServerParameters(command="python", args=["src/server/context_server.py"])
openai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
OPENAI_MODEL = "gpt-4o"
API_KEY = os.getenv("MCP_API_KEY", "")


async def mcp_call(session, tool, **kwargs):
    if API_KEY:
        kwargs["api_key"] = API_KEY
    result = await session.call_tool(tool, arguments=kwargs)
    return result.content[0].text


async def get_system_prompt(session, namespace):
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


async def handle_command(session, cmd, namespace):
    parts = cmd.strip().split(" ", 2)
    verb = parts[0].lower()

    if verb == "/help":
        return (
            "Commands:\n"
            "  /set <key> <value>         store context\n"
            "  /set <key> <value> ttl=60  store with 60s expiry\n"
            "  /get <key>                 retrieve value\n"
            "  /search <query>            search values\n"
            "  /list                      list all keys\n"
            "  /list tag=<tag>            filter by tag\n"
            "  /stats                     server stats\n"
            "  /ns <name>                 switch namespace\n"
            "  /quit                      exit\n"
        ), namespace

    if verb == "/set" and len(parts) >= 3:
        key = parts[1]
        rest = parts[2]
        ttl = 0
        if "ttl=" in rest:
            val_part, ttl_part = rest.rsplit("ttl=", 1)
            try:
                ttl = int(ttl_part.strip())
            except ValueError:
                pass
            value = val_part.strip()
        else:
            value = rest
        msg = await mcp_call(session, "set_context", key=key, value=value, namespace=namespace, ttl_seconds=ttl)
        return msg, namespace

    if verb == "/get" and len(parts) >= 2:
        val = await mcp_call(session, "get_context", key=parts[1], namespace=namespace)
        return f"[{parts[1]}]: {val}", namespace

    if verb == "/search" and len(parts) >= 2:
        result = await mcp_call(session, "search_context", query=parts[1], namespace=namespace)
        return result, namespace

    if verb == "/list":
        tag = ""
        if len(parts) >= 2 and parts[1].startswith("tag="):
            tag = parts[1][4:]
        result = await mcp_call(session, "list_context", namespace=namespace, tag_filter=tag)
        return result, namespace

    if verb == "/stats":
        result = await mcp_call(session, "server_stats")
        return result, namespace

    if verb == "/ns" and len(parts) >= 2:
        return f"Switched to namespace '{parts[1]}'.", parts[1]

    return f"Unknown command '{verb}'. Type /help.", namespace


async def main():
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            namespace = "default"
            history = []

            print("MCP Context Chat — Production")
            print(f"Namespace: '{namespace}' | /help for commands\n")

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

                if user_input.startswith("/"):
                    output, namespace = await handle_command(session, user_input, namespace)
                    print(f"[{namespace}] {output}\n")
                    continue

                system = await get_system_prompt(session, namespace)
                history.append({"role": "user", "content": user_input})
                messages = [{"role": "system", "content": system}] + history

                print("Assistant: ", end="", flush=True)
                reply = ""
                response = await openai.chat.completions.create(
                    model=OPENAI_MODEL, messages=messages, stream=True,
                )
                async for chunk in response:
                    delta = chunk.choices[0].delta.content or ""
                    print(delta, end="", flush=True)
                    reply += delta
                print("\n")
                history.append({"role": "assistant", "content": reply})
                if len(history) > 40:
                    history = history[-40:]


if __name__ == "__main__":
    asyncio.run(main())