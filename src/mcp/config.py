"""
server/config.py — FastAPI server configuration
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

MCP_API_KEY   = os.getenv("MCP_API_KEY", "")
OPENAI_MODEL  = os.getenv("OPENAI_MODEL", "gpt-4o")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
SERVER_SCRIPT = "src/mcp/server.py"