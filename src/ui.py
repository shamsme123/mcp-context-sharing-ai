"""
ui.py — Gradio 6 UI for MCP Context Sharing System
"""

import asyncio
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from typing import Optional

import gradio as gr
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL   = os.getenv("OPENAI_MODEL", "gpt-4o")
DB_PATH        = os.getenv("CONTEXT_DB_PATH", "context_store.db")
API_KEY        = os.getenv("MCP_API_KEY", "")
DEFAULT_TTL    = int(os.getenv("DEFAULT_TTL_SECONDS", "0"))
RATE_LIMIT     = int(os.getenv("RATE_LIMIT_PER_MIN", "60"))

openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# ── DB helpers ───────────────────────────────────────────────────────────────
def _get_db():
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

def _now():
    return datetime.now(timezone.utc).isoformat()

def _is_expired(expires_at):
    if not expires_at:
        return False
    return datetime.fromisoformat(expires_at) < datetime.now(timezone.utc)

def _expires_at(ttl: int) -> Optional[str]:
    if ttl <= 0:
        return None
    return datetime.fromtimestamp(time.time() + ttl, tz=timezone.utc).isoformat()

# ── CRUD ─────────────────────────────────────────────────────────────────────
def db_set(namespace, key, value, tags="", ttl=0):
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    now = _now()
    exp = _expires_at(int(ttl))
    with _get_db() as db:
        existing = db.execute(
            "SELECT key FROM context WHERE namespace=? AND key=?", (namespace, key)
        ).fetchone()
        if existing:
            db.execute(
                "UPDATE context SET value=?, tags=?, updated_at=?, expires_at=? WHERE namespace=? AND key=?",
                (value, json.dumps(tag_list), now, exp, namespace, key)
            )
            return f" Updated '{key}' in '{namespace}'" + (f" (TTL: {ttl}s)" if ttl else "")
        else:
            db.execute(
                "INSERT INTO context VALUES (?,?,?,?,?,?,?,?)",
                (namespace, key, value, json.dumps(tag_list), now, now, exp, None)
            )
            return f" Created '{key}' in '{namespace}'" + (f" (TTL: {ttl}s)" if ttl else "")

def db_get(namespace, key):
    with _get_db() as db:
        row = db.execute(
            "SELECT value, expires_at FROM context WHERE namespace=? AND key=?",
            (namespace, key)
        ).fetchone()
    if not row:
        return f" Key '{key}' not found in '{namespace}'."
    if _is_expired(row["expires_at"]):
        with _get_db() as db:
            db.execute("DELETE FROM context WHERE namespace=? AND key=?", (namespace, key))
        return f" Key '{key}' has expired."
    return row["value"]

def db_list(namespace, tag_filter=""):
    with _get_db() as db:
        rows = db.execute(
            "SELECT key, value, tags, updated_at, expires_at FROM context WHERE namespace=?",
            (namespace,)
        ).fetchall()
    results, expired = [], []
    for row in rows:
        if _is_expired(row["expires_at"]):
            expired.append(row["key"])
            continue
        tag_list = json.loads(row["tags"])
        if tag_filter and tag_filter not in tag_list:
            continue
        results.append({
            "key": row["key"],
            "tags": ", ".join(tag_list) or "—",
            "updated": row["updated_at"][:19],
            "expiry": row["expires_at"][:19] if row["expires_at"] else "never",
            "preview": row["value"][:80] + ("…" if len(row["value"]) > 80 else ""),
        })
    if expired:
        with _get_db() as db:
            db.executemany(
                "DELETE FROM context WHERE namespace=? AND key=?",
                [(namespace, k) for k in expired]
            )
    return results

def db_delete(namespace, key):
    with _get_db() as db:
        cursor = db.execute(
            "DELETE FROM context WHERE namespace=? AND key=?", (namespace, key)
        )
    return f" Deleted '{key}'." if cursor.rowcount else f"❌ Key '{key}' not found."

def db_search(namespace, query):
    with _get_db() as db:
        rows = db.execute(
            "SELECT key, value, tags, expires_at FROM context "
            "WHERE namespace=? AND (value LIKE ? OR key LIKE ?)",
            (namespace, f"%{query}%", f"%{query}%")
        ).fetchall()
    return [
        {"key": r["key"], "tags": ", ".join(json.loads(r["tags"])) or "—",
         "preview": r["value"][:80] + ("…" if len(r["value"]) > 80 else "")}
        for r in rows if not _is_expired(r["expires_at"])
    ]

def db_namespaces():
    with _get_db() as db:
        rows = db.execute(
            "SELECT namespace, COUNT(*) as count FROM context GROUP BY namespace"
        ).fetchall()
    return [{"namespace": r["namespace"], "entries": r["count"]} for r in rows]

def db_stats():
    with _get_db() as db:
        total   = db.execute("SELECT COUNT(*) as n FROM context").fetchone()["n"]
        ns_cnt  = db.execute("SELECT COUNT(DISTINCT namespace) as n FROM context").fetchone()["n"]
        expired = db.execute(
            "SELECT COUNT(*) as n FROM context WHERE expires_at IS NOT NULL AND expires_at < ?",
            (_now(),)
        ).fetchone()["n"]
        tags_rows = db.execute("SELECT tags FROM context").fetchall()
    from collections import Counter
    all_tags = []
    for r in tags_rows:
        all_tags.extend(json.loads(r["tags"]))
    top_tags = Counter(all_tags).most_common(5)
    return {
        "total_entries": total,
        "namespaces": ns_cnt,
        "expired_pending": expired,
        "top_tags": top_tags,
        "auth_enabled": bool(API_KEY),
        "rate_limit": RATE_LIMIT,
        "db_path": DB_PATH,
        "model": OPENAI_MODEL,
    }

# ── OpenAI streaming ─────────────────────────────────────────────────────────
async def _stream_chat(history, namespace):
    rows = db_list(namespace)
    if rows:
        lines = [f"You are a helpful assistant. Use this shared context from namespace '{namespace}':\n"]
        for r in rows:
            full = db_get(namespace, r["key"])
            lines.append(f"[{r['key']}]: {full}")
        system = "\n".join(lines)
    else:
        system = "You are a helpful assistant."

    messages = [{"role": "system", "content": system}]
    for user_msg, bot_msg in history[:-1]:
        messages.append({"role": "user", "content": user_msg})
        messages.append({"role": "assistant", "content": bot_msg or ""})
    messages.append({"role": "user", "content": history[-1][0]})

    response = await openai_client.chat.completions.create(
        model=OPENAI_MODEL, messages=messages, stream=True,
    )
    partial = ""
    async for chunk in response:
        partial += chunk.choices[0].delta.content or ""
        yield partial

def chat_respond(message, history, namespace):
    if not message.strip():
        yield history, ""
        return
    history = history + [[message, None]]

    async def run():
        async for partial in _stream_chat(history, namespace):
            history[-1][1] = partial
            yield history, ""

    loop = asyncio.new_event_loop()
    gen = run()
    try:
        while True:
            try:
                result = loop.run_until_complete(gen.__anext__())
                yield result
            except StopAsyncIteration:
                break
    finally:
        loop.close()

# ── UI ────────────────────────────────────────────────────────────────────────
with gr.Blocks(title="MCP Context Sharing") as app:

    gr.Markdown("# MCP Context Sharing System")
    gr.Markdown("Store shared context via MCP · Chat with OpenAI using that context")

    with gr.Tabs():

        # Tab 1: Chat
        with gr.Tab(" Chat"):
            with gr.Row():
                chat_ns = gr.Dropdown(
                    choices=["default", "project-alpha", "team-standup", "user-42"],
                    value="default",
                    label="Namespace",
                    allow_custom_value=True,
                    scale=1,
                )
                with gr.Column(scale=3):
                    gr.Markdown(
                        "Every message pulls context from the selected namespace "
                        "and injects it into the OpenAI system prompt automatically."
                    )

            chatbot = gr.Chatbot(height=420, show_label=False)
            with gr.Row():
                msg_box = gr.Textbox(
                    placeholder="Ask anything — stored context is injected automatically…",
                    show_label=False,
                    scale=5,
                )
                send_btn = gr.Button("Send", variant="primary", scale=1)
            clear_btn = gr.Button("Clear chat", size="sm")

            send_btn.click(chat_respond, [msg_box, chatbot, chat_ns], [chatbot, msg_box])
            msg_box.submit(chat_respond, [msg_box, chatbot, chat_ns], [chatbot, msg_box])
            clear_btn.click(lambda: ([], ""), outputs=[chatbot, msg_box])

        # Tab 2: Context Manager
        with gr.Tab(" Context Manager"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### Store context")
                    ns_input  = gr.Textbox(value="default", label="Namespace")
                    key_input = gr.Textbox(label="Key")
                    val_input = gr.Textbox(label="Value", lines=4)
                    tag_input = gr.Textbox(label="Tags (comma-separated)", placeholder="goal,important")
                    ttl_input = gr.Number(label="TTL seconds (0 = never)", value=0, precision=0)
                    set_btn   = gr.Button("Store", variant="primary")
                    set_out   = gr.Textbox(label="Result", interactive=False)

                with gr.Column(scale=2):
                    gr.Markdown("### Browse & search")
                    with gr.Row():
                        browse_ns  = gr.Textbox(value="default", label="Namespace", scale=2)
                        tag_filter = gr.Textbox(label="Filter by tag", scale=1)
                        list_btn   = gr.Button("List", scale=1)

                    context_table = gr.Dataframe(
                        headers=["key", "tags", "updated", "expiry", "preview"],
                        datatype=["str", "str", "str", "str", "str"],
                        interactive=False,
                        wrap=True,
                    )

                    with gr.Row():
                        search_q   = gr.Textbox(label="Search query", scale=3)
                        search_btn = gr.Button("Search", scale=1)

                    gr.Markdown("### Get / Delete")
                    with gr.Row():
                        gd_ns  = gr.Textbox(value="default", label="Namespace", scale=1)
                        gd_key = gr.Textbox(label="Key", scale=2)
                    with gr.Row():
                        get_btn = gr.Button("Get value")
                        del_btn = gr.Button("Delete", variant="stop")
                    gd_out = gr.Textbox(label="Result", lines=4, interactive=False)

            def do_set(ns, key, val, tags, ttl):
                if not key or not val:
                    return " Key and Value are required."
                return db_set(ns, key, val, tags, int(ttl))

            def do_list(ns, tag):
                rows = db_list(ns, tag)
                return [[r["key"], r["tags"], r["updated"], r["expiry"], r["preview"]] for r in rows]

            def do_search(ns, query):
                if not query:
                    return []
                rows = db_search(ns, query)
                return [[r["key"], r["tags"], "", "", r["preview"]] for r in rows]

            set_btn.click(do_set, [ns_input, key_input, val_input, tag_input, ttl_input], set_out)
            list_btn.click(do_list, [browse_ns, tag_filter], context_table)
            search_btn.click(do_search, [browse_ns, search_q], context_table)
            get_btn.click(lambda ns, k: db_get(ns, k), [gd_ns, gd_key], gd_out)
            del_btn.click(lambda ns, k: db_delete(ns, k), [gd_ns, gd_key], gd_out)

        # Tab 3: Namespaces
        with gr.Tab(" Namespaces"):
            gr.Markdown("### All namespaces")
            ns_table = gr.Dataframe(
                headers=["namespace", "entries"],
                datatype=["str", "number"],
                interactive=False,
            )
            refresh_ns_btn = gr.Button("Refresh")

            gr.Markdown("### Share context between namespaces")
            with gr.Row():
                share_key    = gr.Textbox(label="Key to share")
                share_src    = gr.Textbox(label="Source namespace")
                share_dst    = gr.Textbox(label="Target namespace")
                share_newkey = gr.Textbox(label="New key name (optional)")
            share_btn = gr.Button("Share", variant="primary")
            share_out = gr.Textbox(label="Result", interactive=False)

            gr.Markdown("### Clear namespace")
            with gr.Row():
                clear_ns_input = gr.Textbox(label="Namespace to clear")
                clear_ns_btn   = gr.Button("Clear all entries", variant="stop")
            clear_ns_out = gr.Textbox(label="Result", interactive=False)

            def do_ns_list():
                rows = db_namespaces()
                return [[r["namespace"], r["entries"]] for r in rows] if rows else []

            def do_share(key, src, dst, new_key):
                if not key or not src or not dst:
                    return " Key, source and target namespace are required."
                with _get_db() as db:
                    row = db.execute(
                        "SELECT * FROM context WHERE namespace=? AND key=?", (src, key)
                    ).fetchone()
                    if not row:
                        return f" Key '{key}' not found in '{src}'."
                    dest_key = new_key.strip() or key
                    db.execute(
                        "INSERT OR REPLACE INTO context VALUES (?,?,?,?,?,?,?,?)",
                        (dst, dest_key, row["value"], row["tags"],
                         row["created_at"], _now(), row["expires_at"], f"{src}/{key}")
                    )
                return f" Shared '{key}' from '{src}' → '{dest_key}' in '{dst}'."

            def do_clear_ns(ns):
                if not ns:
                    return " Namespace is required."
                with _get_db() as db:
                    cursor = db.execute("DELETE FROM context WHERE namespace=?", (ns,))
                return f" Cleared '{ns}' ({cursor.rowcount} entries removed)."

            refresh_ns_btn.click(do_ns_list, outputs=ns_table)
            share_btn.click(do_share, [share_key, share_src, share_dst, share_newkey], share_out)
            clear_ns_btn.click(do_clear_ns, [clear_ns_input], clear_ns_out)
            app.load(do_ns_list, outputs=ns_table)

        # Tab 4: Stats
        with gr.Tab(" Stats"):
            gr.Markdown("### Server health")
            refresh_stats_btn = gr.Button("Refresh stats")
            with gr.Row():
                stat_total = gr.Textbox(label="Total entries",   interactive=False)
                stat_ns    = gr.Textbox(label="Namespaces",      interactive=False)
                stat_exp   = gr.Textbox(label="Expired pending", interactive=False)
                stat_auth  = gr.Textbox(label="Auth enabled",    interactive=False)
            with gr.Row():
                stat_model = gr.Textbox(label="OpenAI model",   interactive=False)
                stat_rate  = gr.Textbox(label="Rate limit/min", interactive=False)
                stat_db    = gr.Textbox(label="Database path",  interactive=False)
            stat_tags = gr.Textbox(label="Top tags", interactive=False)

            def do_stats():
                s = db_stats()
                tags_str = ", ".join(f"{t}({c})" for t, c in s["top_tags"]) or "none"
                return (
                    str(s["total_entries"]),
                    str(s["namespaces"]),
                    str(s["expired_pending"]),
                    "Yes " if s["auth_enabled"] else "No ",
                    s["model"],
                    str(s["rate_limit"]),
                    s["db_path"],
                    tags_str,
                )

            outputs = [stat_total, stat_ns, stat_exp, stat_auth,
                       stat_model, stat_rate, stat_db, stat_tags]
            refresh_stats_btn.click(do_stats, outputs=outputs)
            app.load(do_stats, outputs=outputs)

# ── Launch ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
        theme=gr.themes.Soft(),
    )