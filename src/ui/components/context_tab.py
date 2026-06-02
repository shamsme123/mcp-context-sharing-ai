"""
components/context_tab.py — Context Manager tab
"""

import gradio as gr

from api_client.context import (
    set_context,
    list_context,
    search_context,
    get_context,
    delete_context,
)


def build() -> None:
    """Render the Context Manager tab. Call inside a gr.Tab() context."""
    with gr.Row():

        # ── Left column: Store ────────────────────────────────────────────────
        with gr.Column(scale=1):
            gr.Markdown("### Store context")
            ns_input  = gr.Textbox(value="default", label="Namespace")
            key_input = gr.Textbox(label="Key")
            val_input = gr.Textbox(label="Value", lines=4)
            tag_input = gr.Textbox(label="Tags (comma-separated)", placeholder="goal,important")
            ttl_input = gr.Number(label="TTL seconds (0 = never)", value=0, precision=0)
            set_btn   = gr.Button("Store", variant="primary")
            set_out   = gr.Textbox(label="Result", interactive=False)

        # ── Right column: Browse, search, get/delete ──────────────────────────
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

    # ── Wire up events ────────────────────────────────────────────────────────
    set_btn.click(set_context,    [ns_input, key_input, val_input, tag_input, ttl_input], set_out)
    list_btn.click(list_context,  [browse_ns, tag_filter],  context_table)
    search_btn.click(search_context, [browse_ns, search_q], context_table)
    get_btn.click(get_context,    [gd_ns, gd_key],          gd_out)
    del_btn.click(delete_context, [gd_ns, gd_key],          gd_out)