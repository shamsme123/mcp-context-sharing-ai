"""
commands.py — /command parser and dispatcher for the interactive chat client

All slash-commands are handled here so chat.py stays focused on the
conversation loop.

Exported:
    handle_command(session, cmd, namespace) -> (output: str, namespace: str)
"""


import contextlib
from mcp import ClientSession

from mcp_helper import mcp_call

HELP_TEXT = """\
Commands:
  /set <key> <value>         store context
  /set <key> <value> ttl=60  store with 60s expiry
  /get <key>                 retrieve value
  /search <query>            search values
  /list                      list all keys
  /list tag=<tag>            filter by tag
  /stats                     server stats
  /ns <name>                 switch namespace
  /quit                      exit
"""


async def handle_command(
    session: ClientSession, cmd: str, namespace: str
) -> tuple[str, str]:
    """Parse and execute a slash command.

    Returns
    -------
    (output, namespace)
        output    — string to print to the user
        namespace — current namespace (may have changed via /ns)
    """
    parts = cmd.strip().split(" ", 2)
    verb  = parts[0].lower()

    if verb == "/help":
        return HELP_TEXT, namespace

    if verb == "/set" and len(parts) >= 3:
        key  = parts[1]
        rest = parts[2]
        ttl  = 0
        if "ttl=" in rest:
            val_part, ttl_part = rest.rsplit("ttl=", 1)
            with contextlib.suppress(ValueError):
                ttl = int(ttl_part.strip())
            value = val_part.strip()
        else:
            value = rest
        msg = await mcp_call(
            session, "set_context",
            key=key, value=value, namespace=namespace, ttl_seconds=ttl,
        )
        return msg, namespace

    if verb == "/get" and len(parts) >= 2:
        val = await mcp_call(session, "get_context", key=parts[1], namespace=namespace)
        return f"[{parts[1]}]: {val}", namespace

    if verb == "/search" and len(parts) >= 2:
        result = await mcp_call(session, "search_context", query=parts[1], namespace=namespace)
        return result, namespace

    if verb == "/list":
        tag = parts[1][4:] if len(parts) >= 2 and parts[1].startswith("tag=") else ""
        result = await mcp_call(session, "list_context", namespace=namespace, tag_filter=tag)
        return result, namespace

    if verb == "/stats":
        result = await mcp_call(session, "server_stats")
        return result, namespace

    if verb == "/ns" and len(parts) >= 2:
        new_ns = parts[1]
        return f"Switched to namespace '{new_ns}'.", new_ns

    return f"Unknown command '{verb}'. Type /help.", namespace