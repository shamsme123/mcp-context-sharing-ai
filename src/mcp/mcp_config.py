"""
mcp_config.py — MCP Server Configuration
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Points directly to 'src/mcp' folder
MCP_DIR = Path(__file__).parent.resolve()

# Go up two levels (from src/mcp -> src -> project root) to reach the master .env file
env_path = MCP_DIR.parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

# Server details required by server.py
TRANSPORT = os.getenv("MCP_TRANSPORT", "stdio")  # "stdio" or "sse"
HOST      = os.getenv("MCP_HOST", "127.0.0.1")
PORT      = int(os.getenv("MCP_PORT", "8000"))

# Anchor internal databases and logs cleanly inside the src/mcp/ folder structure
DB_PATH   = str(MCP_DIR / os.getenv("DB_PATH", "context.db"))
LOG_FILE  = str(MCP_DIR / os.getenv("LOG_FILE", "mcp_server.log"))

# Auth and limitations required by tools & auth modules
API_KEY     = os.getenv("MCP_API_KEY", "")
RATE_LIMIT  = int(os.getenv("MCP_RATE_LIMIT", "60"))
DEFAULT_TTL = int(os.getenv("MCP_DEFAULT_TTL", "3600"))