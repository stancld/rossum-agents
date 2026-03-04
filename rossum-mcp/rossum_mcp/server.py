#!/usr/bin/env python3
from __future__ import annotations

import logging
import os
from typing import Literal  # noqa: TC003 - needed at runtime for FastMCP schema generation

from fastmcp import FastMCP
from rossum_api import AsyncRossumAPIClient
from rossum_api.dtos import Token

from rossum_mcp.logging_config import setup_logging
from rossum_mcp.tools import (
    register_create_tools,
    register_delete_tools,
    register_discovery_tools,
    register_get_tools,
    register_update_tools,
)
from rossum_mcp.tools.base import configure, get_mcp_mode, set_mcp_mode

logger = logging.getLogger(__name__)


def create_app() -> FastMCP:
    """Create and configure the MCP server.

    Reads configuration from environment variables:

    - ``ROSSUM_API_BASE_URL`` (required)
    - ``ROSSUM_API_TOKEN`` (required)
    - ``ROSSUM_MCP_MODE`` (optional, default: read-write)
    - ``ROSSUM_MCP_LOG_LEVEL`` (optional, default: INFO)
    """
    setup_logging(log_level=os.environ.get("ROSSUM_MCP_LOG_LEVEL", "INFO"))

    base_url = os.environ["ROSSUM_API_BASE_URL"].rstrip("/")
    api_token = os.environ["ROSSUM_API_TOKEN"]
    mcp_mode = os.environ.get("ROSSUM_MCP_MODE", "read-write")

    configure(base_url=base_url, mcp_mode=mcp_mode)

    logger.info(f"Rossum MCP Server starting in {get_mcp_mode()} mode")

    mcp = FastMCP("rossum-mcp-server")
    client = AsyncRossumAPIClient(base_url=base_url, credentials=Token(token=api_token))

    register_discovery_tools(mcp)
    register_get_tools(mcp, client)
    register_delete_tools(mcp, client)
    register_create_tools(mcp, client)
    register_update_tools(mcp, client)

    @mcp.tool(description="Get the current MCP operation mode (read-only or read-write).")
    async def get_mcp_mode_tool() -> dict:
        return {"mode": get_mcp_mode()}

    @mcp.tool(
        description="Set the MCP operation mode. Use 'read-only' to disable write operations, 'read-write' to enable them."
    )
    async def set_mcp_mode_tool(mode: Literal["read-only", "read-write"]) -> dict:
        try:
            set_mcp_mode(mode)
            current = get_mcp_mode()
            if current == "read-only":
                mcp.disable(tags={"write"})
            else:
                mcp.enable(tags={"write"})
            return {"message": f"MCP mode set to '{current}'"}
        except ValueError as e:
            return {"error": str(e)}

    # Enforce read-only mode by hiding write tools via FastMCP visibility
    if mcp_mode == "read-only":
        mcp.disable(tags={"write"})

    return mcp


def main() -> None:
    """Main entry point for console script."""
    app = create_app()
    app.run()


if __name__ == "__main__":
    main()
