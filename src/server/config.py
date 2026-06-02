"""
config.py — Centralised settings loaded from .env
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


class Settings:
    MCP_API_KEY:    str = os.getenv("MCP_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL:   str = os.getenv("OPENAI_MODEL", "gpt-4o")
    SERVER_SCRIPT:  str = "src/server/context_server.py"

    APP_TITLE:       str = "MCP Context Sharing API"
    APP_DESCRIPTION: str = "REST API wrapping the MCP Context Server. Consumed by the Gradio UI."
    APP_VERSION:     str = "1.0.0"


settings = Settings()