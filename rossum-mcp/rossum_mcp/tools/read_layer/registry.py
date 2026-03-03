"""Entity registry mapping entity names to retrieve/search functions.

Reuses existing private functions from individual tool modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rossum_mcp.tools.annotations import _get_annotation, _list_annotations
from rossum_mcp.tools.document_relations import _get_document_relation, _list_document_relations
from rossum_mcp.tools.email_templates import _get_email_template, _list_email_templates
from rossum_mcp.tools.engines import _get_engine, _list_engines
from rossum_mcp.tools.hooks import _get_hook, _list_hook_logs, _list_hook_templates, _list_hooks
from rossum_mcp.tools.organization_groups import _get_organization_group, _list_organization_groups
from rossum_mcp.tools.organization_limits import _get_organization_limit
from rossum_mcp.tools.queues import _get_queue, _list_queues
from rossum_mcp.tools.relations import _get_relation, _list_relations
from rossum_mcp.tools.rules import _get_rule, _list_rules
from rossum_mcp.tools.schemas.operations import get_schema, list_schemas
from rossum_mcp.tools.users import _get_user, _list_user_roles, _list_users
from rossum_mcp.tools.workspaces import _get_workspace, _list_workspaces

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from rossum_api import AsyncRossumAPIClient

    from rossum_mcp.tools.read_layer.models import SearchQuery


@dataclass
class EntityConfig:
    retrieve_fn: Callable[..., Awaitable[object]] | None
    search_fn: Callable[..., Awaitable[list]] | None


def build_registry(client: AsyncRossumAPIClient) -> dict[str, EntityConfig]:
    return {
        "queue": EntityConfig(
            retrieve_fn=lambda id: _get_queue(client, id),
            search_fn=lambda **kw: _list_queues(client, **kw),
        ),
        "schema": EntityConfig(
            retrieve_fn=lambda id: get_schema(client, id),
            search_fn=lambda **kw: list_schemas(client, **kw),
        ),
        "hook": EntityConfig(
            retrieve_fn=lambda id: _get_hook(client, id),
            search_fn=lambda **kw: _list_hooks(client, **kw),
        ),
        "engine": EntityConfig(
            retrieve_fn=lambda id: _get_engine(client, id),
            search_fn=lambda **kw: _list_engines(client, **kw),
        ),
        "rule": EntityConfig(
            retrieve_fn=lambda id: _get_rule(client, id),
            search_fn=lambda **kw: _list_rules(client, **kw),
        ),
        "user": EntityConfig(
            retrieve_fn=lambda id: _get_user(client, id),
            search_fn=lambda **kw: _list_users(client, **kw),
        ),
        "workspace": EntityConfig(
            retrieve_fn=lambda id: _get_workspace(client, id),
            search_fn=lambda **kw: _list_workspaces(client, **kw),
        ),
        "email_template": EntityConfig(
            retrieve_fn=lambda id: _get_email_template(client, id),
            search_fn=lambda **kw: _list_email_templates(client, **kw),
        ),
        "organization_group": EntityConfig(
            retrieve_fn=lambda id: _get_organization_group(client, id),
            search_fn=lambda **kw: _list_organization_groups(client, **kw),
        ),
        "organization_limit": EntityConfig(
            retrieve_fn=lambda id: _get_organization_limit(client, id),
            search_fn=None,
        ),
        "annotation": EntityConfig(
            retrieve_fn=lambda id: _get_annotation(client, id),
            search_fn=lambda **kw: _list_annotations(client, **kw),
        ),
        "relation": EntityConfig(
            retrieve_fn=lambda id: _get_relation(client, id),
            search_fn=lambda **kw: _list_relations(client, **kw),
        ),
        "document_relation": EntityConfig(
            retrieve_fn=lambda id: _get_document_relation(client, id),
            search_fn=lambda **kw: _list_document_relations(client, **kw),
        ),
        "hook_log": EntityConfig(
            retrieve_fn=None,
            search_fn=lambda **kw: _list_hook_logs(client, **kw),
        ),
        "hook_template": EntityConfig(
            retrieve_fn=None,
            search_fn=lambda **_kw: _list_hook_templates(client),
        ),
        "user_role": EntityConfig(
            retrieve_fn=None,
            search_fn=lambda **_kw: _list_user_roles(client),
        ),
    }


def extract_search_kwargs(query: SearchQuery) -> dict[str, object]:
    """Extract filter kwargs from a search query model, dropping the `entity` discriminator."""
    data = query.model_dump(exclude_none=True)
    data.pop("entity", None)
    return data
