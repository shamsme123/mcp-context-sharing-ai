"""
api_client/chat.py — Chat and stats API calls
"""

from .http import api_post, api_get


def send_message(message: str, namespace: str) -> dict:
    """POST /chat — returns the raw response dict."""
    return api_post("/chat", {"message": message, "namespace": namespace})


def reset_memory(namespace: str) -> str:
    """POST /chat/reset — clears server-side conversation history."""
    res = api_post(f"/chat/reset?namespace={namespace}")
    return res.get("result", res.get("error", "Done."))


def get_stats() -> tuple:
    """GET /stats — returns an 8-tuple for the Stats tab outputs."""
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
        "Yes" if res.get("auth_enabled") else "No",
        str(res.get("model", "—")),
        str(res.get("rate_limit_per_min", "—")),
        str(res.get("db_path", "—")),
        tags_str or "none",
    )