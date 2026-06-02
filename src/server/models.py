"""
models.py — Pydantic request models shared across route files
"""

from typing import Optional
from pydantic import BaseModel


class SetContextRequest(BaseModel):
    namespace:   str = "default"
    key:         str
    value:       str
    tags:        str = ""
    ttl_seconds: int = 0


class ShareContextRequest(BaseModel):
    key:              str
    source_namespace: str
    target_namespace: str
    new_key:          Optional[str] = None


class ChatRequest(BaseModel):
    message:   str
    namespace: str = "default"