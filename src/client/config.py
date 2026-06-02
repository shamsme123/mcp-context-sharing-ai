"""
config.py — Client-side settings loaded from .env
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


class Settings:
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL:   str = os.getenv("OPENAI_MODEL", "gpt-4o")
    MCP_API_KEY:    str = os.getenv("MCP_API_KEY", "")
    SERVER_SCRIPT:  str = "src/mcp/server.py"

    # Default namespace used by the demo
    DEMO_NAMESPACE: str = "project-alpha"


settings = Settings()