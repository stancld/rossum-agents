"""Entity registry mapping entity names to create functions."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from rossum_mcp.tools.email_templates import _create_email_template
from rossum_mcp.tools.engines import _create_engine, _create_engine_field
from rossum_mcp.tools.hooks import _create_hook, _create_hook_from_template
from rossum_mcp.tools.queues import _create_queue_from_template
from rossum_mcp.tools.rules import _create_rule
from rossum_mcp.tools.schemas.operations import create_schema
from rossum_mcp.tools.users import _create_user
from rossum_mcp.tools.workspaces import _create_workspace

if TYPE_CHECKING:
    from rossum_api import AsyncRossumAPIClient

CreateRegistry = dict[str, Callable[..., Awaitable[object]]]


def build_create_registry(client: AsyncRossumAPIClient) -> CreateRegistry:
    return {
        "workspace": lambda **kw: _create_workspace(client, **kw),
        "queue_from_template": lambda **kw: _create_queue_from_template(client, **kw),
        "schema": lambda **kw: create_schema(client, **kw),
        "user": lambda **kw: _create_user(client, **kw),
        "hook": lambda **kw: _create_hook(client, **kw),
        "hook_from_template": lambda **kw: _create_hook_from_template(client, **kw),
        "engine": lambda **kw: _create_engine(client, **kw),
        "engine_field": lambda **kw: _create_engine_field(client, **kw),
        "rule": lambda **kw: _create_rule(client, **kw),
        "email_template": lambda **kw: _create_email_template(client, **kw),
    }
