"""
routes.py — REST API routes exposed via MCP custom_route
Mirrors each MCP tool as a plain HTTP endpoint for the Gradio UI.
All routes live under /api/*
"""

from starlette.requests import Request
from starlette.responses import JSONResponse

from auth import check_request_auth


def register_routes(mcp, tools: dict):
    """
    Register HTTP routes onto the FastMCP instance.
    tools: dict mapping tool names to callables, e.g. {"set_context": set_context_fn}
    """

    @mcp.custom_route("/api/health", methods=["GET"])
    async def api_health(request: Request) -> JSONResponse:
        from mcp.mcp_config import TRANSPORT
        return JSONResponse({"status": "ok", "transport": TRANSPORT})

    @mcp.custom_route("/api/set", methods=["POST"])
    async def api_set(request: Request) -> JSONResponse:
        if err := check_request_auth(request):
            return JSONResponse({"error": err}, status_code=401)
        body = await request.json()
        result = tools["set_context"](
            key=body["key"],
            value=body["value"],
            namespace=body.get("namespace", "default"),
            tags=body.get("tags", ""),
            ttl_seconds=int(body.get("ttl_seconds", 0)),
        )
        return JSONResponse({"result": result})

    @mcp.custom_route("/api/get", methods=["POST"])
    async def api_get(request: Request) -> JSONResponse:
        if err := check_request_auth(request):
            return JSONResponse({"error": err}, status_code=401)
        body = await request.json()
        result = tools["get_context"](
            key=body["key"],
            namespace=body.get("namespace", "default"),
        )
        return JSONResponse({"result": result})

    @mcp.custom_route("/api/list", methods=["POST"])
    async def api_list(request: Request) -> JSONResponse:
        if err := check_request_auth(request):
            return JSONResponse({"error": err}, status_code=401)
        body = await request.json()
        result = tools["list_context"](
            namespace=body.get("namespace", "default"),
            tag_filter=body.get("tag_filter", ""),
        )
        return JSONResponse({"result": result})

    @mcp.custom_route("/api/delete", methods=["POST"])
    async def api_delete(request: Request) -> JSONResponse:
        if err := check_request_auth(request):
            return JSONResponse({"error": err}, status_code=401)
        body = await request.json()
        result = tools["delete_context"](
            key=body["key"],
            namespace=body.get("namespace", "default"),
        )
        return JSONResponse({"result": result})

    @mcp.custom_route("/api/search", methods=["POST"])
    async def api_search(request: Request) -> JSONResponse:
        if err := check_request_auth(request):
            return JSONResponse({"error": err}, status_code=401)
        body = await request.json()
        result = tools["search_context"](
            query=body["query"],
            namespace=body.get("namespace", "default"),
        )
        return JSONResponse({"result": result})

    @mcp.custom_route("/api/share", methods=["POST"])
    async def api_share(request: Request) -> JSONResponse:
        if err := check_request_auth(request):
            return JSONResponse({"error": err}, status_code=401)
        body = await request.json()
        result = tools["share_context"](
            key=body["key"],
            source_namespace=body["source_namespace"],
            target_namespace=body["target_namespace"],
            new_key=body.get("new_key"),
        )
        return JSONResponse({"result": result})

    @mcp.custom_route("/api/namespaces", methods=["GET"])
    async def api_namespaces(request: Request) -> JSONResponse:
        if err := check_request_auth(request):
            return JSONResponse({"error": err}, status_code=401)
        result = tools["list_namespaces"]()
        return JSONResponse({"result": result})

    @mcp.custom_route("/api/clear", methods=["POST"])
    async def api_clear(request: Request) -> JSONResponse:
        if err := check_request_auth(request):
            return JSONResponse({"error": err}, status_code=401)
        body = await request.json()
        result = tools["clear_namespace"](namespace=body["namespace"])
        return JSONResponse({"result": result})

    @mcp.custom_route("/api/stats", methods=["GET"])
    async def api_stats(request: Request) -> JSONResponse:
        if err := check_request_auth(request):
            return JSONResponse({"error": err}, status_code=401)
        result = tools["server_stats"]()
        return JSONResponse({"result": result})