"""
namespace_routes.py — /namespaces/* endpoints
"""

import json

from fastapi import APIRouter

from mcp_client import mcp_call

router = APIRouter(prefix="/namespaces", tags=["namespaces"])


@router.get("", summary="List all namespaces")
async def list_namespaces():
    result = await mcp_call("list_namespaces")
    try:
        return {"namespaces": json.loads(result)}
    except Exception:
        return {"namespaces": {}, "message": result}


@router.delete("/{namespace}", summary="Clear all entries in a namespace")
async def clear_namespace(namespace: str):
    result = await mcp_call("clear_namespace", namespace=namespace)
    return {"result": result}