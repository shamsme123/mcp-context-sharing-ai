"""
context_routes.py — /context/* endpoints
"""

import json

from fastapi import APIRouter, HTTPException, Query

from mcp_client import mcp_call
from models import SetContextRequest, ShareContextRequest

router = APIRouter(prefix="/context", tags=["context"])


@router.post("/set", summary="Store a context entry")
async def set_context(req: SetContextRequest):
    result = await mcp_call(
        "set_context",
        key=req.key, value=req.value,
        namespace=req.namespace, tags=req.tags,
        ttl_seconds=req.ttl_seconds,
    )
    return {"result": result}


@router.get("/get/{namespace}/{key}", summary="Retrieve a context entry")
async def get_context(namespace: str, key: str):
    result = await mcp_call("get_context", key=key, namespace=namespace)
    if "not found" in result:
        raise HTTPException(status_code=404, detail=result)
    return {"key": key, "namespace": namespace, "value": result}


@router.get("/list/{namespace}", summary="List all entries in a namespace")
async def list_context(namespace: str, tag_filter: str = Query(default="")):
    result = await mcp_call("list_context", namespace=namespace, tag_filter=tag_filter)
    try:
        return {"namespace": namespace, "entries": json.loads(result)}
    except Exception:
        return {"namespace": namespace, "entries": [], "message": result}


@router.delete("/delete/{namespace}/{key}", summary="Delete a context entry")
async def delete_context(namespace: str, key: str):
    result = await mcp_call("delete_context", key=key, namespace=namespace)
    return {"result": result}


@router.get("/search/{namespace}", summary="Search context entries")
async def search_context(namespace: str, query: str = Query(...)):
    result = await mcp_call("search_context", query=query, namespace=namespace)
    try:
        return {"namespace": namespace, "matches": json.loads(result)}
    except Exception:
        return {"namespace": namespace, "matches": [], "message": result}


@router.post("/share", summary="Share a context entry between namespaces")
async def share_context(req: ShareContextRequest):
    result = await mcp_call(
        "share_context",
        key=req.key,
        source_namespace=req.source_namespace,
        target_namespace=req.target_namespace,
        new_key=req.new_key,
    )
    return {"result": result}