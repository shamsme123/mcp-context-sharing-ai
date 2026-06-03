"""
database.py — SQLite persistence layer
All raw DB operations live here. No MCP or business logic.
"""

import json
import sqlite3
import time
from datetime import datetime, timezone
from typing import Optional

from mcp_config import DB_PATH


# ── Connection ────────────────────────────────────────────────────────────────
def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS context (
            namespace   TEXT NOT NULL,
            key         TEXT NOT NULL,
            value       TEXT NOT NULL,
            tags        TEXT NOT NULL DEFAULT '[]',
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL,
            expires_at  TEXT,
            shared_from TEXT,
            PRIMARY KEY (namespace, key)
        )
    """)
    conn.commit()
    return conn


# ── Time helpers ──────────────────────────────────────────────────────────────
def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def expires_at(ttl: int) -> Optional[str]:
    if ttl <= 0:
        return None
    return datetime.fromtimestamp(time.time() + ttl, tz=timezone.utc).isoformat()


def is_expired(exp: Optional[str]) -> bool:
    if not exp:
        return False
    return datetime.fromisoformat(exp) < datetime.now(timezone.utc)


# ── CRUD operations ───────────────────────────────────────────────────────────
def upsert_entry(namespace: str, key: str, value: str,
                 tag_list: list, exp: Optional[str]) -> str:
    """Insert or update a context entry. Returns 'created' or 'updated'."""
    ts = now()
    with get_db() as db:
        if existing := db.execute(
            "SELECT key FROM context WHERE namespace=? AND key=?",
            (namespace, key),
        ).fetchone():
            db.execute(
                "UPDATE context SET value=?, tags=?, updated_at=?, expires_at=? "
                "WHERE namespace=? AND key=?",
                (value, json.dumps(tag_list), ts, exp, namespace, key)
            )
            return "updated"
        db.execute(
            "INSERT INTO context VALUES (?,?,?,?,?,?,?,?)",
            (namespace, key, value, json.dumps(tag_list), ts, ts, exp, None)
        )
        return "created"


def fetch_entry(namespace: str, key: str) -> Optional[sqlite3.Row]:
    with get_db() as db:
        return db.execute(
            "SELECT value, expires_at FROM context WHERE namespace=? AND key=?",
            (namespace, key)
        ).fetchone()


def remove_entry(namespace: str, key: str) -> int:
    with get_db() as db:
        cursor = db.execute(
            "DELETE FROM context WHERE namespace=? AND key=?", (namespace, key)
        )
    return cursor.rowcount


def fetch_namespace(namespace: str) -> list:
    with get_db() as db:
        return db.execute(
            "SELECT key, value, tags, updated_at, expires_at FROM context WHERE namespace=?",
            (namespace,)
        ).fetchall()


def remove_expired_keys(namespace: str, keys: list):
    with get_db() as db:
        db.executemany(
            "DELETE FROM context WHERE namespace=? AND key=?",
            [(namespace, k) for k in keys]
        )


def search_entries(namespace: str, query: str) -> list:
    with get_db() as db:
        return db.execute(
            "SELECT key, value, tags, expires_at FROM context "
            "WHERE namespace=? AND (value LIKE ? OR key LIKE ?)",
            (namespace, f"%{query}%", f"%{query}%")
        ).fetchall()


def copy_entry(source_ns: str, key: str, target_ns: str, dest_key: str):
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM context WHERE namespace=? AND key=?", (source_ns, key)
        ).fetchone()
        if not row:
            return None
        db.execute(
            "INSERT OR REPLACE INTO context VALUES (?,?,?,?,?,?,?,?)",
            (target_ns, dest_key, row["value"], row["tags"],
             row["created_at"], now(), row["expires_at"], f"{source_ns}/{key}")
        )
        return row


def fetch_all_namespaces() -> list:
    with get_db() as db:
        return db.execute(
            "SELECT namespace, COUNT(*) as count FROM context GROUP BY namespace"
        ).fetchall()


def remove_namespace(namespace: str) -> int:
    with get_db() as db:
        cursor = db.execute("DELETE FROM context WHERE namespace=?", (namespace,))
    return cursor.rowcount


def fetch_stats() -> dict:
    with get_db() as db:
        total   = db.execute("SELECT COUNT(*) as n FROM context").fetchone()["n"]
        ns_cnt  = db.execute("SELECT COUNT(DISTINCT namespace) as n FROM context").fetchone()["n"]
        expired = db.execute(
            "SELECT COUNT(*) as n FROM context WHERE expires_at IS NOT NULL AND expires_at < ?",
            (now(),)
        ).fetchone()["n"]
    return {"total": total, "namespaces": ns_cnt, "expired": expired}