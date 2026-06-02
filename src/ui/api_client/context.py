"""
api_client/context.py — Context and namespace API calls
"""

from .http import api_get, api_post, api_delete


# ── Context CRUD ──────────────────────────────────────────────────────────────

def set_context(namespace: str, key: str, value: str, tags: str, ttl: int) -> str:
    if not key or not value:
        return "Key and Value are required."
    res = api_post("/context/set", {
        "namespace": namespace, "key": key, "value": value,
        "tags": tags, "ttl_seconds": int(ttl),
    })
    return res.get("result", res.get("error", "Unknown error"))


def list_context(namespace: str, tag_filter: str = "") -> list[list]:
    res = api_get(f"/context/list/{namespace}", {"tag_filter": tag_filter} if tag_filter else None)
    if "error" in res:
        return [[res["error"], "", "", "", ""]]
    entries = res.get("entries", [])
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


def search_context(namespace: str, query: str) -> list[list]:
    if not query:
        return []
    res = api_get(f"/context/search/{namespace}", {"query": query})
    if "error" in res:
        return [[res["error"], "", "", "", ""]]
    rows = []
    for m in res.get("matches", []):
        tags = m.get("tags", [])
        tags_str = ", ".join(tags) if isinstance(tags, list) else str(tags)
        rows.append([m.get("key", ""), tags_str or "—", "", "", m.get("preview", "")])
    return rows


def get_context(namespace: str, key: str) -> str:
    if not key:
        return "Key is required."
    res = api_get(f"/context/get/{namespace}/{key}")
    if "error" in res:
        return res["error"]
    return res.get("value", "Not found.")


def delete_context(namespace: str, key: str) -> str:
    if not key:
        return "Key is required."
    res = api_delete(f"/context/delete/{namespace}/{key}")
    return res.get("result", res.get("error", "Unknown error"))


# ── Namespace operations ──────────────────────────────────────────────────────

def list_namespaces() -> list[list]:
    res = api_get("/namespaces")
    if "error" in res:
        return [[res["error"], ""]]
    ns = res.get("namespaces", {})
    return [[k, v] for k, v in ns.items()] if ns else []


def share_context(key: str, src: str, dst: str, new_key: str) -> str:
    if not key or not src or not dst:
        return "Key, source and target namespace are required."
    res = api_post("/context/share", {
        "key": key, "source_namespace": src,
        "target_namespace": dst, "new_key": new_key or None,
    })
    return res.get("result", res.get("error", "Unknown error"))


def clear_namespace(namespace: str) -> str:
    if not namespace:
        return "Namespace is required."
    res = api_delete(f"/namespaces/{namespace}")
    return res.get("result", res.get("error", "Unknown error"))