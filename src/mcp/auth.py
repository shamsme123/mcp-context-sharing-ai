"""
auth.py — API key authentication and rate limiting
"""

import time
from mcp_config import API_KEY, RATE_LIMIT

# ── Rate limiter ──────────────────────────────────────────────────────────────
_rate_buckets: dict[str, list[float]] = {}


def check_rate(client_id: str = "default") -> bool:
    """Return True if request is within rate limit, False if exceeded."""
    now = time.time()
    window = _rate_buckets.setdefault(client_id, [])
    _rate_buckets[client_id] = [t for t in window if now - t < 60]
    if len(_rate_buckets[client_id]) >= RATE_LIMIT:
        return False
    _rate_buckets[client_id].append(now)
    return True


# ── Auth ──────────────────────────────────────────────────────────────────────
def check_auth(api_key: str = "") -> bool:
    """Return True if auth passes (or auth is disabled)."""
# sourcery api_key == API_KEY if API_KEY else True
    return api_key == API_KEY if API_KEY else True


def check_request_auth(request) -> str | None:
    """
    Check auth from HTTP request headers.
    Returns error message string if failed, None if passed.
    Checks X-API-Key header or Bearer token.
    """
    if not API_KEY:
        return None
    key = (
        request.headers.get("X-API-Key", "")
        or request.headers.get("Authorization", "").removeprefix("Bearer ")
    )
    return "Invalid API key." if key != API_KEY else None