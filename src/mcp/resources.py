"""
resources.py — MCP Resources and Prompts
"""

import json
from database import get_db, is_expired


def register_resources(mcp):
    """Register all resources and prompts onto the FastMCP instance."""

    @mcp.resource("context://{namespace}/{key}")
    def get_context_resource(namespace: str, key: str) -> str:
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM context WHERE namespace=? AND key=?", (namespace, key)
            ).fetchone()
        if not row or is_expired(row["expires_at"]):
            return f"Not found or expired: {namespace}/{key}"
        return json.dumps(dict(row), indent=2)

    @mcp.resource("context://{namespace}")
    def get_namespace_resource(namespace: str) -> str:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM context WHERE namespace=?", (namespace,)
            ).fetchall()
        active = [dict(r) for r in rows if not is_expired(r["expires_at"])]
        return json.dumps(active, indent=2) if active else f"Namespace '{namespace}' is empty."

    @mcp.prompt()
    def summarize_namespace(namespace: str = "default") -> str:
        with get_db() as db:
            rows = db.execute(
                "SELECT key, value, expires_at FROM context WHERE namespace=?", (namespace,)
            ).fetchall()
        active = [(r["key"], r["value"]) for r in rows if not is_expired(r["expires_at"])]
        if not active:
            return f"The namespace '{namespace}' is empty."
        entries_text = "\n\n".join(f"[{k}]\n{v}" for k, v in active)
        return (
            f"Here is all context stored in namespace '{namespace}':\n\n"
            f"{entries_text}\n\n"
            "Please provide a concise summary of the key information above."
        )