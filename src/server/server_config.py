"""
server_config.py — Centralised settings loaded from .env
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Points to 'D:\Context Sharing System using MCP'
ROOT_DIR = Path(__file__).parent.parent.parent
env_path = ROOT_DIR / ".env"

# Debug helper: confirms if the app is physically reading the file
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)
else:
    print(f"⚠️ WARNING: .env file not found at expected path: {env_path.resolve()}")


class Settings:
    MCP_API_KEY:    str = os.getenv("MCP_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL:   str = os.getenv("OPENAI_MODEL", "gpt-4o")
    
    # Points cleanly to src/mcp/server.py
    SERVER_SCRIPT:  str = str(ROOT_DIR / "src" / "mcp" / "server.py")

    APP_TITLE:       str = "MCP Context Sharing API"
    APP_DESCRIPTION: str = "REST API wrapping the MCP Context Server. Consumed by the Gradio UI."
    APP_VERSION:     str = "1.0.0"


settings = Settings()