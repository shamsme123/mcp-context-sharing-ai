"""
components/stats_tab.py — Stats tab
"""

import gradio as gr

from api_client.chat import get_stats


def build(app: gr.Blocks) -> None:
    """Render the Stats tab. Call inside a gr.Tab() context.

    Parameters
    ----------
    app:
        The top-level gr.Blocks instance, needed to register app.load handlers.
    """
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

    refresh_stats_btn.click(get_stats, outputs=outputs)
    app.load(get_stats, outputs=outputs)