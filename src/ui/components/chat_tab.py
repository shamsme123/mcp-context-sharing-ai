"""
components/chat_tab.py — Chat tab
"""

import gradio as gr
from gradio import ChatMessage

from api_client.chat import send_message, reset_memory


def chat_respond(message: str, history: list, namespace: str):
    if not message.strip():
        yield history, ""
        return

    res = send_message(message, namespace)

    if "error" in res:
        reply = res["error"]
    else:
        reply    = res.get("reply", "No response.")
        ctx_keys = res.get("context_keys", [])
        mem      = res.get("memory_turns", 0)
        if ctx_keys:
            reply += f"\n\n_Context used: {', '.join(ctx_keys)} | Turn: {mem}_"

    history = history + [
        ChatMessage(role="user",      content=message),
        ChatMessage(role="assistant", content=reply),
    ]
    yield history, ""


def reset_chat(namespace: str) -> tuple:
    result = reset_memory(namespace)
    return [], result


def build() -> None:
    """Render the Chat tab. Call inside a gr.Tab() context."""
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
        clear_btn = gr.Button("Clear chat",     size="sm")
        reset_btn = gr.Button("Reset memory",   size="sm", variant="stop")

    status_box = gr.Textbox(label="Status", interactive=False)

    send_btn.click(chat_respond,  [msg_box, chatbot, chat_ns], [chatbot, msg_box])
    msg_box.submit(chat_respond,  [msg_box, chatbot, chat_ns], [chatbot, msg_box])
    clear_btn.click(lambda: ([], ""),              outputs=[chatbot, msg_box])
    reset_btn.click(reset_chat,   [chat_ns],       [chatbot, status_box])