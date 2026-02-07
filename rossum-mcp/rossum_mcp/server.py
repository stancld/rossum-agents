#!/usr/bin/env python3
"""Rossum MCP Server

Provides tools for uploading documents and retrieving annotations using Rossum API.
Built with FastMCP for a cleaner, more Pythonic interface.
"""

from __future__ import annotations

import logging
import os

from fastmcp import FastMCP
from rossum_api import AsyncRossumAPIClient
from rossum_api.dtos import Token

from rossum_mcp.logging_config import setup_logging
from rossum_mcp.tools import (
    register_annotation_tools,
    register_discovery_tools,
    register_document_relation_tools,
    register_email_template_tools,
    register_engine_tools,
    register_hook_tools,
    register_queue_tools,
    register_relation_tools,
    register_rule_tools,
    register_schema_tools,
    register_user_tools,
    register_workspace_tools,
)
from rossum_mcp.tools.base import get_mcp_mode, set_mcp_mode

setup_logging(log_level="DEBUG", use_console=False)

logger = logging.getLogger(__name__)

BASE_URL = os.environ["ROSSUM_API_BASE_URL"].rstrip("/")
API_TOKEN = os.environ["ROSSUM_API_TOKEN"]

logger.info(f"Rossum MCP Server starting in {get_mcp_mode()} mode")

mcp = FastMCP("rossum-mcp-server")
client = AsyncRossumAPIClient(base_url=BASE_URL, credentials=Token(token=API_TOKEN))

register_discovery_tools(mcp)
register_annotation_tools(mcp, client)
register_queue_tools(mcp, client)
register_schema_tools(mcp, client)
register_engine_tools(mcp, client)
register_hook_tools(mcp, client)
register_email_template_tools(mcp, client)
register_document_relation_tools(mcp, client)
register_relation_tools(mcp, client)
register_rule_tools(mcp, client)
register_user_tools(mcp, client)
register_workspace_tools(mcp, client)


@mcp.tool(description="Get the current MCP operation mode (read-only or read-write).")
async def get_mcp_mode_tool() -> dict:
    return {"mode": get_mcp_mode()}


@mcp.tool(
    description="Set the MCP operation mode. Use 'read-only' to disable write operations, 'read-write' to enable them."
)
async def set_mcp_mode_tool(mode: str) -> dict:
    try:
        set_mcp_mode(mode)
        return {"message": f"MCP mode set to '{get_mcp_mode()}'"}
    except ValueError as e:
        return {"error": str(e)}


def main() -> None:
    """Main entry point for console script."""
    mcp.run()


if __name__ == "__main__":
    main()
