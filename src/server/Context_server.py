"""
MCP Context Sharing Server — Production Ready
────────────────────────────────────────────────
Upgrades over dev version:
  1. SQLite persistence  — context survives restarts
  2. TTL expiry          — entries auto-expire
  3. API key auth        — protect the server
  4. Rate limiting       — prevent abuse
  5. Structured logging  — JSON logs to file + stderr
  6. SSE transport       — HTTP server for production
"""

import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

# ── Config ─────────────────────────────────────────────────────────────────
DB_PATH        = os.getenv("CONTEXT_DB_PATH", "context_store.db")
API_KEY        = os.getenv("MCP_API_KEY", "")          # empty = auth disabled
RATE_LIMIT     = int(os.getenv("RATE_LIMIT_PER_MIN", "60"))
DEFAULT_TTL    = int(os.getenv("DEFAULT_TTL_SECONDS", "0"))  # 0 = no expiry
LOG_FILE       = os.getenv("LOG_FILE", "mcp_server.log")
HOST           = os.getenv("MCP_HOST", "0.0.0.0")
PORT           = int(os.getenv("MCP_PORT", "8000"))
TRANSPORT      = os.getenv("MCP_TRANSPORT", "stdio")   # stdio | sse

# ── Logging ────────────────────────────────────────────────────────────────
class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            "ts":      datetime.now(timezone.utc).isoformat(),
            "level":   record.levelname,
            "msg":     record.getMessage(),
            "logger":  record.name,
        })

logger = logging.getLogger("mcp-context")
logger.setLevel(logging.INFO)

_fh = logging.FileHandler(LOG_FILE)
_fh.setFormatter(JsonFormatter())
logger.addHandler(_fh)

_sh = logging.StreamHandler()
_sh.setFormatter(JsonFormatter())
logger.addHandler(_sh)

# ── Rate limiter ────────────────────────────────────────────────────────────
_rate_buckets: dict[str, list[float]] = {}

def _check_rate(client_id: str = "default") -> bool:
    now = time.time()
    window = _rate_buckets.setdefault(client_id, [])
    _rate_buckets[client_id] = [t for t in window if now - t < 60]
    if len(_rate_buckets[client_id]) >= RATE_LIMIT:
        return False
    _rate_buckets[client_id].append(now)
    return True

# ── SQLite persistence ──────────────────────────────────────────────────────
def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS context (
            namespace  TEXT NOT NULL,
            key        TEXT NOT NULL,
            value      TEXT NOT NULL,
            tags       TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            expires_at TEXT,
            shared_from TEXT,
            PRIMARY KEY (namespace, key)
        )
    """)
    conn.commit()
    return conn

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _expires_at(ttl: int) -> Optional[str]:
    if ttl <= 0:
        return None
    return datetime.fromtimestamp(time.time() + ttl, tz=timezone.utc).isoformat()

def _is_expired(expires_at: Optional[str]) -> bool:
    if not expires_at:
        return False
    return datetime.fromisoformat(expires_at) < datetime.now(timezone.utc)

def _auth_check(api_key_header: str = "") -> bool:
    if not API_KEY:
        return True
    return api_key_header == API_KEY

# ── MCP Server ──────────────────────────────────────────────────────────────
mcp = FastMCP("context-sharing-server")

# ── Tools ───────────────────────────────────────────────────────────────────

@mcp.tool()
def set_context(
    key: str,
    value: str,
    namespace: str = "default",
    tags: str = "",
    ttl_seconds: int = 0,
    api_key: str = "",
) -> str:
    """
    Store a value. Optionally set TTL (seconds until expiry, 0=forever).
    Pass api_key if server auth is enabled.
    """
    if not _auth_check(api_key):
        logger.warning({"action": "set_context", "result": "auth_failed", "namespace": namespace, "key": key})
        return "Error: Invalid API key."
    if not _check_rate():
        return "Error: Rate limit exceeded. Try again in a minute."

    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    now = _now()
    effective_ttl = ttl_seconds if ttl_seconds > 0 else DEFAULT_TTL
    exp = _expires_at(effective_ttl)

    with _get_db() as db:
        existing = db.execute(
            "SELECT key FROM context WHERE namespace=? AND key=?", (namespace, key)
        ).fetchone()
        if existing:
            db.execute(
                "UPDATE context SET value=?, tags=?, updated_at=?, expires_at=? WHERE namespace=? AND key=?",
                (value, json.dumps(tag_list), now, exp, namespace, key)
            )
            action = "updated"
        else:
            db.execute(
                "INSERT INTO context VALUES (?,?,?,?,?,?,?,?)",
                (namespace, key, value, json.dumps(tag_list), now, now, exp, None)
            )
            action = "created"

    logger.info({"action": "set_context", "namespace": namespace, "key": key, "result": action, "ttl": effective_ttl})
    ttl_note = f" (expires in {effective_ttl}s)" if exp else ""
    return f"{action.capitalize()} '{key}' in '{namespace}'{ttl_note}."


@mcp.tool()
def get_context(key: str, namespace: str = "default", api_key: str = "") -> str:
    """Retrieve a value by key."""
    if not _auth_check(api_key):
        return "Error: Invalid API key."
    if not _check_rate():
        return "Error: Rate limit exceeded."

    with _get_db() as db:
        row = db.execute(
            "SELECT value, expires_at FROM context WHERE namespace=? AND key=?",
            (namespace, key)
        ).fetchone()

    if not row:
        return f"Key '{key}' not found in '{namespace}'."
    if _is_expired(row["expires_at"]):
        with _get_db() as db:
            db.execute("DELETE FROM context WHERE namespace=? AND key=?", (namespace, key))
        return f"Key '{key}' has expired and was removed."

    logger.info({"action": "get_context", "namespace": namespace, "key": key})
    return row["value"]


@mcp.tool()
def list_context(namespace: str = "default", tag_filter: str = "", api_key: str = "") -> str:
    """List all keys in a namespace. Expired entries are auto-removed."""
    if not _auth_check(api_key):
        return "Error: Invalid API key."
    if not _check_rate():
        return "Error: Rate limit exceeded."

    with _get_db() as db:
        rows = db.execute(
            "SELECT key, value, tags, updated_at, expires_at FROM context WHERE namespace=?",
            (namespace,)
        ).fetchall()

    now = datetime.now(timezone.utc)
    results = []
    expired_keys = []

    for row in rows:
        if _is_expired(row["expires_at"]):
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
        with _get_db() as db:
            db.executemany(
                "DELETE FROM context WHERE namespace=? AND key=?",
                [(namespace, k) for k in expired_keys]
            )

    if not results:
        return f"No entries in namespace '{namespace}'" + (f" with tag '{tag_filter}'" if tag_filter else "") + "."
    return json.dumps(results, indent=2)


@mcp.tool()
def delete_context(key: str, namespace: str = "default", api_key: str = "") -> str:
    """Delete a context entry."""
    if not _auth_check(api_key):
        return "Error: Invalid API key."

    with _get_db() as db:
        cursor = db.execute(
            "DELETE FROM context WHERE namespace=? AND key=?", (namespace, key)
        )
    if cursor.rowcount == 0:
        return f"Key '{key}' not found in '{namespace}'."
    logger.info({"action": "delete_context", "namespace": namespace, "key": key})
    return f"Deleted '{key}' from '{namespace}'."


@mcp.tool()
def search_context(query: str, namespace: str = "default", api_key: str = "") -> str:
    """Full-text search across all values in a namespace."""
    if not _auth_check(api_key):
        return "Error: Invalid API key."
    if not _check_rate():
        return "Error: Rate limit exceeded."

    with _get_db() as db:
        rows = db.execute(
            "SELECT key, value, tags, expires_at FROM context WHERE namespace=? AND (value LIKE ? OR key LIKE ?)",
            (namespace, f"%{query}%", f"%{query}%")
        ).fetchall()

    matches = [
        {"key": r["key"], "tags": json.loads(r["tags"]), "preview": r["value"][:100]}
        for r in rows if not _is_expired(r["expires_at"])
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
    if not _auth_check(api_key):
        return "Error: Invalid API key."

    with _get_db() as db:
        row = db.execute(
            "SELECT * FROM context WHERE namespace=? AND key=?", (source_namespace, key)
        ).fetchone()
        if not row:
            return f"Key '{key}' not found in '{source_namespace}'."
        if _is_expired(row["expires_at"]):
            return f"Key '{key}' has expired."

        dest_key = new_key or key
        now = _now()
        db.execute(
            "INSERT OR REPLACE INTO context VALUES (?,?,?,?,?,?,?,?)",
            (target_namespace, dest_key, row["value"], row["tags"], row["created_at"], now, row["expires_at"], f"{source_namespace}/{key}")
        )

    logger.info({"action": "share_context", "from": f"{source_namespace}/{key}", "to": f"{target_namespace}/{dest_key}"})
    return f"Shared '{key}' from '{source_namespace}' → '{dest_key}' in '{target_namespace}'."


@mcp.tool()
def list_namespaces(api_key: str = "") -> str:
    """List all namespaces and their entry counts."""
    if not _auth_check(api_key):
        return "Error: Invalid API key."

    with _get_db() as db:
        rows = db.execute(
            "SELECT namespace, COUNT(*) as count FROM context GROUP BY namespace"
        ).fetchall()

    if not rows:
        return "No namespaces yet."
    return json.dumps({r["namespace"]: r["count"] for r in rows}, indent=2)


@mcp.tool()
def clear_namespace(namespace: str, api_key: str = "") -> str:
    """Delete all entries in a namespace."""
    if not _auth_check(api_key):
        return "Error: Invalid API key."

    with _get_db() as db:
        cursor = db.execute("DELETE FROM context WHERE namespace=?", (namespace,))
    count = cursor.rowcount
    logger.info({"action": "clear_namespace", "namespace": namespace, "deleted": count})
    return f"Cleared '{namespace}' ({count} entries removed)."


@mcp.tool()
def server_stats(api_key: str = "") -> str:
    """Return server stats: total entries, namespaces, expired count."""
    if not _auth_check(api_key):
        return "Error: Invalid API key."

    with _get_db() as db:
        total = db.execute("SELECT COUNT(*) as n FROM context").fetchone()["n"]
        ns_count = db.execute("SELECT COUNT(DISTINCT namespace) as n FROM context").fetchone()["n"]
        now = _now()
        expired = db.execute(
            "SELECT COUNT(*) as n FROM context WHERE expires_at IS NOT NULL AND expires_at < ?", (now,)
        ).fetchone()["n"]

    return json.dumps({
        "total_entries": total,
        "namespaces": ns_count,
        "expired_pending_cleanup": expired,
        "rate_limit_per_min": RATE_LIMIT,
        "auth_enabled": bool(API_KEY),
        "db_path": DB_PATH,
        "transport": TRANSPORT,
    }, indent=2)


# ── Resources ───────────────────────────────────────────────────────────────

@mcp.resource("context://{namespace}/{key}")
def get_context_resource(namespace: str, key: str) -> str:
    with _get_db() as db:
        row = db.execute(
            "SELECT * FROM context WHERE namespace=? AND key=?", (namespace, key)
        ).fetchone()
    if not row or _is_expired(row["expires_at"]):
        return f"Not found or expired: {namespace}/{key}"
    return json.dumps(dict(row), indent=2)


@mcp.resource("context://{namespace}")
def get_namespace_resource(namespace: str) -> str:
    with _get_db() as db:
        rows = db.execute(
            "SELECT * FROM context WHERE namespace=?", (namespace,)
        ).fetchall()
    active = [dict(r) for r in rows if not _is_expired(r["expires_at"])]
    return json.dumps(active, indent=2) if active else f"Namespace '{namespace}' is empty."


# ── Prompts ─────────────────────────────────────────────────────────────────

@mcp.prompt()
def summarize_namespace(namespace: str = "default") -> str:
    with _get_db() as db:
        rows = db.execute(
            "SELECT key, value, expires_at FROM context WHERE namespace=?", (namespace,)
        ).fetchall()
    active = [(r["key"], r["value"]) for r in rows if not _is_expired(r["expires_at"])]
    if not active:
        return f"The namespace '{namespace}' is empty."
    entries_text = "\n\n".join(f"[{k}]\n{v}" for k, v in active)
    return (
        f"Here is all context stored in namespace '{namespace}':\n\n"
        f"{entries_text}\n\n"
        "Please provide a concise summary of the key information above."
    )


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info({"action": "startup", "transport": TRANSPORT, "db": DB_PATH, "auth": bool(API_KEY)})
    if TRANSPORT == "sse":
        mcp.run(transport="sse", host=HOST, port=PORT)
    else:
        mcp.run()