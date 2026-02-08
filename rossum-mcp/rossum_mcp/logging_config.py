from __future__ import annotations

import logging
import sys


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Configure logging for the MCP server.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
                   Falls back to INFO on invalid values.
    """
    root_logger = logging.getLogger()

    normalized = log_level.upper()
    level = logging.getLevelNamesMapping().get(normalized, logging.INFO)
    root_logger.setLevel(level)

    root_logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(formatter)
    root_logger.addHandler(console)

    return root_logger
