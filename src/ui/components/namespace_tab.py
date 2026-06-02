"""
components/namespace_tab.py — 🗃️ Namespaces tab
"""

import gradio as gr

from api_client.context import list_namespaces, share_context, clear_namespace


def build(app: gr.Blocks) -> None:
    """Render the Namespaces tab. Call inside a gr.Tab() context.

    Parameters
    ----------
    app:
        The top-level gr.Blocks instance, needed to register app.load handlers.
    """
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

    # ── Wire up events ────────────────────────────────────────────────────────
    refresh_ns_btn.click(list_namespaces, outputs=ns_table)
    share_btn.click(share_context, [share_key, share_src, share_dst, share_newkey], share_out)
    clear_ns_btn.click(clear_namespace, [clear_ns_input], clear_ns_out)
    app.load(list_namespaces, outputs=ns_table)