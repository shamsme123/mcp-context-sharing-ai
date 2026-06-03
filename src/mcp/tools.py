"""
tools.py — All MCP tools (set, get, list, delete, search, share, namespaces, stats)
Registered on the FastMCP instance passed in from server.py
"""

import json
from typing import Optional

from mcp_config import API_KEY, DEFAULT_TTL, RATE_LIMIT, DB_PATH, TRANSPORT
from auth import check_auth, check_rate
from database import (
    upsert_entry, fetch_entry, remove_entry, fetch_namespace,
    remove_expired_keys, search_entries, copy_entry,
    fetch_all_namespaces, remove_namespace, fetch_stats,
    expires_at, is_expired,
)
from logger import logger


def register_tools(mcp):
    """Register all tools onto the FastMCP instance."""

    @mcp.tool()
    def set_context(
        key: str,
        value: str,
        namespace: str = "default",
        tags: str = "",
        ttl_seconds: int = 0,
        api_key: str = "",
    ) -> str:
        """Store a value. Optionally set TTL (seconds until expiry, 0=forever)."""
        # FIX 1: Strip namespace and key to prevent leading/trailing space bugs
        namespace = namespace.strip()
        key = key.strip()

        if not check_auth(api_key):
            logger.warning({"action": "set_context", "result": "auth_failed", "namespace": namespace, "key": key})
            return "Error: Invalid API key."
        if not check_rate():
            return "Error: Rate limit exceeded. Try again in a minute."

        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        # FIX 2: ttl_seconds=0 means "no expiry" — do NOT fall back to DEFAULT_TTL
        effective_ttl = ttl_seconds if ttl_seconds > 0 else 0
        exp = expires_at(effective_ttl)  # expires_at(0) returns None → stored forever
        action = upsert_entry(namespace, key, value, tag_list, exp)

        logger.info({"action": "set_context", "namespace": namespace, "key": key, "result": action})
        ttl_note = f" (expires in {effective_ttl}s)" if exp else ""
        return f"{action.capitalize()} '{key}' in '{namespace}'{ttl_note}."


    @mcp.tool()
    def get_context(key: str, namespace: str = "default", api_key: str = "") -> str:
        """Retrieve a value by key."""
        # FIX: Strip to match stored keys correctly
        namespace = namespace.strip()
        key = key.strip()

        if not check_auth(api_key):
            return "Error: Invalid API key."
        if not check_rate():
            return "Error: Rate limit exceeded."

        row = fetch_entry(namespace, key)
        if not row:
            return f"Key '{key}' not found in '{namespace}'."
        if is_expired(row["expires_at"]):
            remove_entry(namespace, key)
            return f"Key '{key}' has expired and was removed."

        logger.info({"action": "get_context", "namespace": namespace, "key": key})
        return row["value"]


    @mcp.tool()
    def list_context(namespace: str = "default", tag_filter: str = "", api_key: str = "") -> str:
        """List all keys in a namespace. Expired entries are auto-removed."""
        # FIX: Strip namespace so " project-alpha" and "project-alpha" resolve the same
        namespace = namespace.strip()

        if not check_auth(api_key):
            return "Error: Invalid API key."
        if not check_rate():
            return "Error: Rate limit exceeded."

        rows = fetch_namespace(namespace)
        results = []
        expired_keys = []

        for row in rows:
            if is_expired(row["expires_at"]):
                expired_keys.append(row["key"])
                continue
            tag_list = json.loads(row["tags"])
            if tag_filter and tag_filter not in tag_list:
                continue
            results.append({
                "key": row["key"],
                "tags": tag_list,
                "updated_at": row["updated_at"],
                "expires_at": row["expires_at"],
                "preview": row["value"][:100] + ("…" if len(row["value"]) > 100 else ""),
            })

        if expired_keys:
            remove_expired_keys(namespace, expired_keys)

        if not results:
            return f"No entries in namespace '{namespace}'" + (f" with tag '{tag_filter}'" if tag_filter else "") + "."
        return json.dumps(results, indent=2)


    @mcp.tool()
    def delete_context(key: str, namespace: str = "default", api_key: str = "") -> str:
        """Delete a context entry."""
        # FIX: Strip to match stored keys correctly
        namespace = namespace.strip()
        key = key.strip()

        if not check_auth(api_key):
            return "Error: Invalid API key."

        count = remove_entry(namespace, key)
        if count == 0:
            return f"Key '{key}' not found in '{namespace}'."
        logger.info({"action": "delete_context", "namespace": namespace, "key": key})
        return f"Deleted '{key}' from '{namespace}'."


    @mcp.tool()
    def search_context(query: str, namespace: str = "default", api_key: str = "") -> str:
        """Full-text search across all values in a namespace."""
        # FIX: Strip namespace for consistent lookup
        namespace = namespace.strip()

        if not check_auth(api_key):
            return "Error: Invalid API key."
        if not check_rate():
            return "Error: Rate limit exceeded."

        rows = search_entries(namespace, query)
        matches = [
            {"key": r["key"], "tags": json.loads(r["tags"]), "preview": r["value"][:100]}
            for r in rows if not is_expired(r["expires_at"])
        ]
        if not matches:
            return f"No matches for '{query}' in '{namespace}'."
        return json.dumps(matches, indent=2)


    @mcp.tool()
    def share_context(
        key: str,
        source_namespace: str,
        target_namespace: str,
        new_key: Optional[str] = None,
        api_key: str = "",
    ) -> str:
        """Copy a context entry from one namespace to another."""
        # FIX: Strip all namespace/key inputs
        source_namespace = source_namespace.strip()
        target_namespace = target_namespace.strip()
        key = key.strip()

        if not check_auth(api_key):
            return "Error: Invalid API key."

        dest_key = (new_key.strip() if new_key else None) or key
        row = copy_entry(source_namespace, key, target_namespace, dest_key)
        if row is None:
            return f"Key '{key}' not found in '{source_namespace}'."
        if is_expired(row["expires_at"]):
            return f"Key '{key}' has expired."

        logger.info({"action": "share_context", "from": f"{source_namespace}/{key}", "to": f"{target_namespace}/{dest_key}"})
        return f"Shared '{key}' from '{source_namespace}' → '{dest_key}' in '{target_namespace}'."


    @mcp.tool()
    def list_namespaces(api_key: str = "") -> str:
        """List all namespaces and their entry counts."""
        if not check_auth(api_key):
            return "Error: Invalid API key."

        rows = fetch_all_namespaces()
        if not rows:
            return "No namespaces yet."
        return json.dumps({r["namespace"]: r["count"] for r in rows}, indent=2)


    @mcp.tool()
    def clear_namespace(namespace: str, api_key: str = "") -> str:
        """Delete all entries in a namespace."""
        # FIX: Strip namespace
        namespace = namespace.strip()

        if not check_auth(api_key):
            return "Error: Invalid API key."

        count = remove_namespace(namespace)
        logger.info({"action": "clear_namespace", "namespace": namespace, "deleted": count})
        return f"Cleared '{namespace}' ({count} entries removed)."


    @mcp.tool()
    def server_stats(api_key: str = "") -> str:
        """Return server stats: total entries, namespaces, expired count."""
        if not check_auth(api_key):
            return "Error: Invalid API key."

        stats = fetch_stats()
        return json.dumps({
            "total_entries": stats["total"],
            "namespaces": stats["namespaces"],
            "expired_pending_cleanup": stats["expired"],
            "rate_limit_per_min": RATE_LIMIT,
            "auth_enabled": bool(API_KEY),
            "db_path": DB_PATH,
            "transport": TRANSPORT,
        }, indent=2)