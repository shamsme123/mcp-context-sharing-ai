"""
ui.py — Gradio UI → FastAPI → MCP Server → SQLite
"""

import os
import requests
import gradio as gr
from gradio import ChatMessage
from dotenv import load_dotenv

load_dotenv()

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")


# ── API client helpers ────────────────────────────────────────────────────────
def api_get(path, params=None):
    try:
        r = requests.get(f"{API_BASE}{path}", params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        return {"error": "❌ FastAPI not running. Start it with: python src/api.py"}
    except Exception as e:
        return {"error": str(e)}


def api_post(path, data=None):
    try:
        r = requests.post(f"{API_BASE}{path}", json=data, timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        return {"error": "❌ FastAPI not running. Start it with: python src/api.py"}
    except Exception as e:
        return {"error": str(e)}


def api_delete(path):
    try:
        r = requests.delete(f"{API_BASE}{path}", timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        return {"error": "❌ FastAPI not running. Start it with: python src/api.py"}
    except Exception as e:
        return {"error": str(e)}


# ── Chat ──────────────────────────────────────────────────────────────────────
def chat_respond(message, history, namespace):
    if not message.strip():
        yield history, ""
        return

    res = api_post("/chat", {"message": message, "namespace": namespace})

    if "error" in res:
        reply = res["error"]
    else:
        reply = res.get("reply", "No response.")
        ctx_keys = res.get("context_keys", [])
        mem      = res.get("memory_turns", 0)
        if ctx_keys:
            reply += f"\n\n_Context used: {', '.join(ctx_keys)} | Turn: {mem}_"

    history = history + [ChatMessage(role="user", content=message), ChatMessage(role="assistant", content=reply)]
    yield history, ""


def reset_chat(namespace):
    res = api_post(f"/chat/reset?namespace={namespace}")
    return [], res.get("result", res.get("error", "Done."))


# ── Context CRUD ──────────────────────────────────────────────────────────────
def do_set(ns, key, val, tags, ttl):
    if not key or not val:
        return "⚠️ Key and Value are required."
    res = api_post("/context/set", {
        "namespace": ns, "key": key, "value": val,
        "tags": tags, "ttl_seconds": int(ttl),
    })
    return res.get("result", res.get("error", "Unknown error"))


def do_list(ns, tag):
    res = api_get(f"/context/list/{ns}", {"tag_filter": tag} if tag else None)
    if "error" in res:
        return [[res["error"], "", "", "", ""]]
    entries = res.get("entries", [])
    if not entries:
        return []
    rows = []
    for e in entries:
        tags = e.get("tags", [])
        tags_str = ", ".join(tags) if isinstance(tags, list) else str(tags)
        rows.append([
            e.get("key", ""),
            tags_str or "—",
            e.get("updated_at", "")[:19],
            e.get("expires_at", "never")[:19] if e.get("expires_at") else "never",
            e.get("preview", e.get("value", ""))[:80],
        ])
    return rows


def do_search(ns, query):
    if not query:
        return []
    res = api_get(f"/context/search/{ns}", {"query": query})
    if "error" in res:
        return [[res["error"], "", "", "", ""]]
    matches = res.get("matches", [])
    rows = []
    for m in matches:
        tags = m.get("tags", [])
        tags_str = ", ".join(tags) if isinstance(tags, list) else str(tags)
        rows.append([m.get("key", ""), tags_str or "—", "", "", m.get("preview", "")])
    return rows


def do_get(ns, key):
    if not key:
        return "⚠️ Key is required."
    res = api_get(f"/context/get/{ns}/{key}")
    if "error" in res:
        return res["error"]
    return res.get("value", "Not found.")


def do_delete(ns, key):
    if not key:
        return "⚠️ Key is required."
    res = api_delete(f"/context/delete/{ns}/{key}")
    return res.get("result", res.get("error", "Unknown error"))


# ── Namespaces ────────────────────────────────────────────────────────────────
def do_ns_list():
    res = api_get("/namespaces")
    if "error" in res:
        return [[res["error"], ""]]
    ns = res.get("namespaces", {})
    return [[k, v] for k, v in ns.items()] if ns else []


def do_share(key, src, dst, new_key):
    if not key or not src or not dst:
        return "⚠️ Key, source and target namespace are required."
    res = api_post("/context/share", {
        "key": key, "source_namespace": src,
        "target_namespace": dst, "new_key": new_key or None,
    })
    return res.get("result", res.get("error", "Unknown error"))


def do_clear_ns(ns):
    if not ns:
        return "⚠️ Namespace is required."
    res = api_delete(f"/namespaces/{ns}")
    return res.get("result", res.get("error", "Unknown error"))


# ── Stats ─────────────────────────────────────────────────────────────────────
def do_stats():
    res = api_get("/stats")
    if "error" in res:
        err = res["error"]
        return (err,) + ("",) * 7
    tags = res.get("top_tags", [])
    tags_str = ", ".join(f"{t}({c})" for t, c in tags) if isinstance(tags, list) else str(tags)
    return (
        str(res.get("total_entries", "—")),
        str(res.get("namespaces", "—")),
        str(res.get("expired_pending_cleanup", "—")),
        "Yes 🔒" if res.get("auth_enabled") else "No 🔓",
        str(res.get("model", "—")),
        str(res.get("rate_limit_per_min", "—")),
        str(res.get("db_path", "—")),
        tags_str or "none",
    )


# ── UI ────────────────────────────────────────────────────────────────────────
with gr.Blocks(title="MCP Context Sharing") as app:

    gr.Markdown("# MCP Context Sharing System")
    gr.Markdown(
        "**Architecture:** Gradio UI → FastAPI (port 8000) → MCP Server → SQLite  \n"
        "**Stack:** OpenAI · MCP · FastAPI · Gradio"
    )

    with gr.Tabs():

        # Tab 1: Chat
        with gr.Tab("💬 Chat"):
            with gr.Row():
                chat_ns = gr.Dropdown(
                    choices=["default", "project-alpha", "team-standup", "user-42"],
                    value="default", label="Namespace",
                    allow_custom_value=True, scale=1,
                )
                with gr.Column(scale=3):
                    gr.Markdown(
                        "Every message fetches context from **MCP Server via FastAPI** "
                        "and injects it into the OpenAI system prompt automatically."
                    )

            chatbot = gr.Chatbot(height=420, show_label=False)
            with gr.Row():
                msg_box  = gr.Textbox(
                    placeholder="Ask anything — MCP context injected via FastAPI…",
                    show_label=False, scale=5,
                )
                send_btn = gr.Button("Send", variant="primary", scale=1)
            with gr.Row():
                clear_btn  = gr.Button("Clear chat", size="sm")
                reset_btn  = gr.Button("Reset memory", size="sm", variant="stop")
            status_box = gr.Textbox(label="Status", interactive=False)

            send_btn.click(chat_respond, [msg_box, chatbot, chat_ns], [chatbot, msg_box])
            msg_box.submit(chat_respond, [msg_box, chatbot, chat_ns], [chatbot, msg_box])
            clear_btn.click(lambda: ([], ""), outputs=[chatbot, msg_box])
            reset_btn.click(reset_chat, [chat_ns], [chatbot, status_box])

        # Tab 2: Context Manager
        with gr.Tab("🗂️ Context Manager"):
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
                        interactive=False, wrap=True,
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

            set_btn.click(do_set, [ns_input, key_input, val_input, tag_input, ttl_input], set_out)
            list_btn.click(do_list, [browse_ns, tag_filter], context_table)
            search_btn.click(do_search, [browse_ns, search_q], context_table)
            get_btn.click(do_get, [gd_ns, gd_key], gd_out)
            del_btn.click(do_delete, [gd_ns, gd_key], gd_out)

        # Tab 3: Namespaces
        with gr.Tab("🗃️ Namespaces"):
            gr.Markdown("### All namespaces")
            ns_table = gr.Dataframe(
                headers=["namespace", "entries"],
                datatype=["str", "number"], interactive=False,
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

            refresh_ns_btn.click(do_ns_list, outputs=ns_table)
            share_btn.click(do_share, [share_key, share_src, share_dst, share_newkey], share_out)
            clear_ns_btn.click(do_clear_ns, [clear_ns_input], clear_ns_out)
            app.load(do_ns_list, outputs=ns_table)

        # Tab 4: Stats
        with gr.Tab("📊 Stats"):
            gr.Markdown("### Server health — data from FastAPI → MCP Server")
            refresh_stats_btn = gr.Button("Refresh stats")
            with gr.Row():
                stat_total = gr.Textbox(label="Total entries",   interactive=False)
                stat_ns    = gr.Textbox(label="Namespaces",      interactive=False)
                stat_exp   = gr.Textbox(label="Expired pending", interactive=False)
                stat_auth  = gr.Textbox(label="Auth enabled",    interactive=False)
            with gr.Row():
                stat_model = gr.Textbox(label="OpenAI model",    interactive=False)
                stat_rate  = gr.Textbox(label="Rate limit/min",  interactive=False)
                stat_db    = gr.Textbox(label="Database path",   interactive=False)
                stat_tags  = gr.Textbox(label="Top tags",        interactive=False)

            outputs = [stat_total, stat_ns, stat_exp, stat_auth,
                       stat_model, stat_rate, stat_db, stat_tags]
            refresh_stats_btn.click(do_stats, outputs=outputs)
            app.load(do_stats, outputs=outputs)


if __name__ == "__main__":
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        show_error=True,
        theme=gr.themes.Soft(),
    )