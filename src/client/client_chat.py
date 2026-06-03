"""
chat.py — Interactive terminal chat with MCP context + OpenAI streaming

Run:
    python src/client/chat.py
"""

import asyncio

from openai import AsyncOpenAI
from mcp.client.stdio import stdio_client
from mcp import ClientSession

from client_config import settings
from mcp_helper import SERVER_PARAMS, get_system_prompt
from commands import handle_command

openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

MAX_HISTORY = 40  # total messages kept (user + assistant)


async def main() -> None:
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            namespace = "default"
            history:  list[dict] = []

            print("MCP Context Chat")
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

                # ── Regular chat message ──────────────────────────────────────
                system = await get_system_prompt(session, namespace)
                history.append({"role": "user", "content": user_input})
                messages = [{"role": "system", "content": system}] + history

                print("Assistant: ", end="", flush=True)
                reply = ""
                response = await openai.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=messages,
                    stream=True,
                )
                async for chunk in response:
                    delta = chunk.choices[0].delta.content or ""
                    print(delta, end="", flush=True)
                    reply += delta
                print("\n")

                history.append({"role": "assistant", "content": reply})
                if len(history) > MAX_HISTORY:
                    history = history[-MAX_HISTORY:]


if __name__ == "__main__":
    asyncio.run(main())