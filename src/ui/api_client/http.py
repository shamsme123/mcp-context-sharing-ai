"""
api_client/http.py — Raw HTTP helpers (GET / POST / DELETE)

All API calls in this project go through these three functions so
connection errors and HTTP errors are handled in one place.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

_START_HINT = "FastAPI not running. Start it with: python src/server/app.py"


def api_get(path: str, params: dict | None = None) -> dict:
    try:
        r = requests.get(f"{API_BASE}{path}", params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        return {"error": _START_HINT}
    except Exception as e:
        return {"error": str(e)}


def api_post(path: str, data: dict | None = None) -> dict:
    try:
        r = requests.post(f"{API_BASE}{path}", json=data, timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        return {"error": _START_HINT}
    except Exception as e:
        return {"error": str(e)}


def api_delete(path: str) -> dict:
    try:
        r = requests.delete(f"{API_BASE}{path}", timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        return {"error": _START_HINT}
    except Exception as e:
        return {"error": str(e)}