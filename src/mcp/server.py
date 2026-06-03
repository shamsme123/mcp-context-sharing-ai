"""
server.py — MCP Context Sharing Server entry point
Wires together: config → logger → tools → resources → routes
"""

from mcp.server.fastmcp import FastMCP
from mcp_config import TRANSPORT, HOST, PORT, DB_PATH
from logger import logger

# ── Create MCP instance ───────────────────────────────────────────────────────
mcp = FastMCP("context-sharing-server")

# ── Register everything ───────────────────────────────────────────────────────
from tools import register_tools
from resources import register_resources

register_tools(mcp)
register_resources(mcp)

# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info({"action": "startup", "transport": TRANSPORT, "db": DB_PATH})
    if TRANSPORT == "sse":
        mcp.run(transport="sse", host=HOST, port=PORT)
    else:
        mcp.run()