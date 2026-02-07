from __future__ import annotations

import logging
import sys


def setup_logging(
    app_name: str = "rossum-mcp",
    log_level: str = "DEBUG",
    log_file: str | None = None,
    use_console: bool = True,
) -> logging.Logger:
    """Configure logging with optional console handler.

    Args:
        app_name: Application name for logging context
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (reserved for future use)
        use_console: Whether to add console handler (default: True)

    Returns:
        Configured root logger
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    root_logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    if use_console:
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(formatter)
        root_logger.addHandler(console)

    return root_logger
