"""
app.py — Gradio UI entry point
───────────────────────────────
Architecture:
    Gradio UI → FastAPI (port 8000) → MCP Server → SQLite

Module layout:
    api_client/http.py          — raw GET / POST / DELETE
    api_client/context.py       — context + namespace API calls
    api_client/chat.py          — chat + stats API calls
    components/chat_tab.py      — Chat tab
    components/context_tab.py   — Context Manager tab
    components/namespace_tab.py — Namespaces tab
    components/stats_tab.py     — Stats tab

Run:
    python src/ui/app.py
"""

import gradio as gr

from components import chat_tab, context_tab, namespace_tab, stats_tab

with gr.Blocks(title="MCP Context Sharing") as app:

    gr.Markdown("# MCP Context Sharing System")
    gr.Markdown(
        "**Architecture:** Gradio UI → FastAPI (port 8000) → MCP Server → SQLite  \n"
        "**Stack:** OpenAI · MCP · FastAPI · Gradio"
    )

    with gr.Tabs():
        with gr.Tab("Chat"):
            chat_tab.build()

        with gr.Tab("Context Manager"):
            context_tab.build()

        with gr.Tab("Namespaces"):
            namespace_tab.build(app)

        with gr.Tab("Stats"):
            stats_tab.build(app)


if __name__ == "__main__":
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        show_error=True,
        theme=gr.themes.Soft(),
    )