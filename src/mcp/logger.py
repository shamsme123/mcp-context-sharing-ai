"""
logger.py — Structured JSON logging to file and stderr
"""

import json
import logging
from datetime import datetime, timezone
from mcp_config import LOG_FILE


class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            "ts":     datetime.now(timezone.utc).isoformat(),
            "level":  record.levelname,
            "msg":    record.getMessage(),
            "logger": record.name,
        })


def get_logger(name: str = "mcp-context") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # already configured

    logger.setLevel(logging.INFO)

    fh = logging.FileHandler(LOG_FILE)
    fh.setFormatter(JsonFormatter())
    logger.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setFormatter(JsonFormatter())
    logger.addHandler(sh)

    return logger


logger = get_logger()