"""
MCP Context Sharing Server
Allows multiple agents/clients to store, retrieve, and share context.
"""

from mcp.server.fastmcp import FastMCP
from datetime import datetime
from typing import Optional
import json

# Initialize the MCP server
mcp = FastMCP("context-sharing-server")

# ---------------------------------------------------------------------------
# In-memory context store
# Structure: { namespace: { key: { value, tags, created_at, updated_at } } }
# ---------------------------------------------------------------------------
_store: dict[str, dict[str, dict]] = {}


# ── Helpers ────────────────────────────────────────────────────────────────

def _ns(namespace: str) -> dict:
    """Return (creating if needed) the dict for a namespace."""
    if namespace not in _store:
        _store[namespace] = {}
    return _store[namespace]


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


# ── Tools ──────────────────────────────────────────────────────────────────

@mcp.tool()
def set_context(
    key: str,
    value: str,
    namespace: str = "default",
    tags: str = "",
) -> str:
    """
    Store a piece of context.

    Args:
        key:       Unique identifier for this context entry.
        value:     The content to store (string / JSON string / plain text).
        namespace: Logical group (e.g. 'project-alpha', 'user-42'). Defaults to 'default'.
        tags:      Comma-separated labels for filtering (e.g. 'summary,important').

    Returns:
        Confirmation message.
    """
    ns = _ns(namespace)
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    now = _now()

    if key in ns:
        ns[key].update({"value": value, "tags": tag_list, "updated_at": now})
        return f"✅ Updated '{key}' in namespace '{namespace}'."
    else:
        ns[key] = {
            "value": value,
            "tags": tag_list,
            "created_at": now,
            "updated_at": now,
        }
        return f"✅ Created '{key}' in namespace '{namespace}'."


@mcp.tool()
def get_context(key: str, namespace: str = "default") -> str:
    """
    Retrieve a context entry by key.

    Args:
        key:       The identifier used when storing.
        namespace: The namespace to look in. Defaults to 'default'.

    Returns:
        The stored value, or an error message if not found.
    """
    entry = _ns(namespace).get(key)
    if entry is None:
        return f"❌ Key '{key}' not found in namespace '{namespace}'."
    return entry["value"]


@mcp.tool()
def list_context(namespace: str = "default", tag_filter: str = "") -> str:
    """
    List all context keys in a namespace, optionally filtered by tag.

    Args:
        namespace:  The namespace to inspect. Defaults to 'default'.
        tag_filter: If given, only entries that carry this tag are returned.

    Returns:
        JSON array of entry summaries.
    """
    ns = _ns(namespace)
    results = []
    for key, entry in ns.items():
        if tag_filter and tag_filter not in entry.get("tags", []):
            continue
        results.append({
            "key": key,
            "tags": entry.get("tags", []),
            "created_at": entry.get("created_at"),
            "updated_at": entry.get("updated_at"),
            "preview": entry["value"][:120] + ("…" if len(entry["value"]) > 120 else ""),
        })
    if not results:
        msg = f"No entries in namespace '{namespace}'"
        if tag_filter:
            msg += f" with tag '{tag_filter}'"
        return msg + "."
    return json.dumps(results, indent=2)


@mcp.tool()
def delete_context(key: str, namespace: str = "default") -> str:
    """
    Delete a context entry.

    Args:
        key:       The identifier to remove.
        namespace: The namespace to look in. Defaults to 'default'.

    Returns:
        Confirmation or error message.
    """
    ns = _ns(namespace)
    if key not in ns:
        return f"❌ Key '{key}' not found in namespace '{namespace}'."
    del ns[key]
    return f"🗑️ Deleted '{key}' from namespace '{namespace}'."


@mcp.tool()
def search_context(query: str, namespace: str = "default") -> str:
    """
    Full-text search across all context values in a namespace.

    Args:
        query:     Substring to search for (case-insensitive).
        namespace: The namespace to search. Defaults to 'default'.

    Returns:
        JSON array of matching entry summaries.
    """
    ns = _ns(namespace)
    q = query.lower()
    matches = []
    for key, entry in ns.items():
        if q in entry["value"].lower() or q in key.lower():
            matches.append({
                "key": key,
                "tags": entry.get("tags", []),
                "preview": entry["value"][:120] + ("…" if len(entry["value"]) > 120 else ""),
            })
    if not matches:
        return f"No matches for '{query}' in namespace '{namespace}'."
    return json.dumps(matches, indent=2)


@mcp.tool()
def share_context(
    key: str,
    source_namespace: str,
    target_namespace: str,
    new_key: Optional[str] = None,
) -> str:
    """
    Copy a context entry from one namespace to another.

    Args:
        key:              The key to copy.
        source_namespace: Where to copy from.
        target_namespace: Where to copy to.
        new_key:          Optional new key name in the target namespace.

    Returns:
        Confirmation or error message.
    """
    src = _ns(source_namespace)
    if key not in src:
        return f"❌ Key '{key}' not found in namespace '{source_namespace}'."

    dest_key = new_key or key
    entry = src[key]
    _ns(target_namespace)[dest_key] = {
        **entry,
        "updated_at": _now(),
        "shared_from": f"{source_namespace}/{key}",
    }
    return (
        f"🔗 Shared '{key}' from '{source_namespace}' "
        f"→ '{dest_key}' in '{target_namespace}'."
    )


@mcp.tool()
def list_namespaces() -> str:
    """
    List all existing namespaces and their entry counts.

    Returns:
        JSON object mapping namespace names to their entry counts.
    """
    summary = {ns: len(entries) for ns, entries in _store.items()}
    if not summary:
        return "No namespaces exist yet."
    return json.dumps(summary, indent=2)


@mcp.tool()
def clear_namespace(namespace: str) -> str:
    """
    Delete ALL context entries in a namespace.

    Args:
        namespace: The namespace to wipe.

    Returns:
        Confirmation message.
    """
    if namespace not in _store:
        return f"Namespace '{namespace}' does not exist."
    count = len(_store[namespace])
    del _store[namespace]
    return f"🗑️ Cleared namespace '{namespace}' ({count} entries removed)."


# ── Resources ──────────────────────────────────────────────────────────────

@mcp.resource("context://{namespace}/{key}")
def get_context_resource(namespace: str, key: str) -> str:
    """Expose a single context entry as an MCP resource."""
    entry = _store.get(namespace, {}).get(key)
    if entry is None:
        return f"Not found: {namespace}/{key}"
    return json.dumps(entry, indent=2)


@mcp.resource("context://{namespace}")
def get_namespace_resource(namespace: str) -> str:
    """Expose an entire namespace as an MCP resource."""
    ns = _store.get(namespace, {})
    if not ns:
        return f"Namespace '{namespace}' is empty or does not exist."
    return json.dumps(ns, indent=2)


# ── Prompts ────────────────────────────────────────────────────────────────

@mcp.prompt()
def summarize_namespace(namespace: str = "default") -> str:
    """Generate a prompt asking Claude to summarize all context in a namespace."""
    ns = _store.get(namespace, {})
    if not ns:
        return f"The namespace '{namespace}' is empty."
    entries_text = "\n\n".join(
        f"[{key}]\n{entry['value']}" for key, entry in ns.items()
    )
    return (
        f"Here is all context stored in namespace '{namespace}':\n\n"
        f"{entries_text}\n\n"
        "Please provide a concise summary of the key information above."
    )


# ── Entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()