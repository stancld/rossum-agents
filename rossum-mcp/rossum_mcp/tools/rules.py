from __future__ import annotations

import logging
from dataclasses import asdict
from typing import TYPE_CHECKING

from rossum_api.domain_logic.resources import Resource
from rossum_api.models.rule import Rule, RuleAction

from rossum_mcp.tools.base import build_resource_url, delete_resource, graceful_list, is_read_write_mode

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


def _actions_to_dicts(actions: list[RuleAction]) -> list[dict]:
    """Serialize actions for API payloads, handling both dataclass instances and raw dicts."""
    return [asdict(a) if isinstance(a, RuleAction) else a for a in actions]


async def _get_rule(client: AsyncRossumAPIClient, rule_id: int) -> Rule:
    logger.debug(f"Retrieving rule: rule_id={rule_id}")
    rule: Rule = await client.retrieve_rule(rule_id)
    return rule


async def _list_rules(
    client: AsyncRossumAPIClient,
    schema_id: int | None = None,
    organization_id: int | None = None,
    enabled: bool | None = None,
) -> list[Rule]:
    logger.debug(f"Listing rules: schema_id={schema_id}, organization_id={organization_id}, enabled={enabled}")
    filters: dict = {}
    if schema_id is not None:
        filters["schema"] = schema_id
    if organization_id is not None:
        filters["organization"] = organization_id
    if enabled is not None:
        filters["enabled"] = enabled

    result = await graceful_list(client, Resource.Rule, "rule", **filters)
    return result.items


async def _create_rule(
    client: AsyncRossumAPIClient,
    name: str,
    trigger_condition: str,
    actions: list[RuleAction],
    enabled: bool = True,
    schema_id: int | None = None,
    queue_ids: list[int] | None = None,
) -> Rule | dict:
    if not is_read_write_mode():
        return {"error": "create_rule is not available in read-only mode"}

    if schema_id is None and not queue_ids:
        return {"error": "Provide at least one of schema_id or queue_ids to scope the rule."}

    logger.info(f"Creating rule: name={name}, schema_id={schema_id}, enabled={enabled}")

    rule_data: dict = {
        "name": name,
        "trigger_condition": trigger_condition,
        "actions": _actions_to_dicts(actions),
        "enabled": enabled,
    }

    if schema_id is not None:
        rule_data["schema"] = build_resource_url("schemas", schema_id)

    if queue_ids is not None:
        rule_data["queues"] = [build_resource_url("queues", qid) for qid in queue_ids]

    logger.debug(f"Rule creation payload: {rule_data}")
    rule: Rule = await client.create_new_rule(rule_data)
    logger.info(f"Successfully created rule: id={rule.id}, name={rule.name}")
    return rule


async def _update_rule(
    client: AsyncRossumAPIClient,
    rule_id: int,
    name: str,
    trigger_condition: str,
    actions: list[RuleAction],
    enabled: bool,
    queue_ids: list[int],
) -> Rule | dict:
    """Full update (PUT) - all fields required."""
    if not is_read_write_mode():
        return {"error": "update_rule is not available in read-only mode"}

    logger.info(f"Updating rule: rule_id={rule_id}, name={name}")
    existing_rule: Rule = await client.retrieve_rule(rule_id)

    rule_data: dict = {
        "name": name,
        "trigger_condition": trigger_condition,
        "actions": _actions_to_dicts(actions),
        "enabled": enabled,
        "queues": [build_resource_url("queues", qid) for qid in queue_ids],
    }

    if existing_rule.schema is not None:
        rule_data["schema"] = existing_rule.schema

    logger.debug(f"Rule update payload: {rule_data}")
    await client._http_client.update(Resource.Rule, rule_id, rule_data)
    updated_rule: Rule = await client.retrieve_rule(rule_id)
    logger.info(f"Successfully updated rule: id={updated_rule.id}")
    return updated_rule


async def _patch_rule(
    client: AsyncRossumAPIClient,
    rule_id: int,
    name: str | None = None,
    trigger_condition: str | None = None,
    actions: list[RuleAction] | None = None,
    enabled: bool | None = None,
    queue_ids: list[int] | None = None,
) -> Rule | dict:
    """Partial update (PATCH) - only provided fields are updated."""
    if not is_read_write_mode():
        return {"error": "patch_rule is not available in read-only mode"}

    logger.info(f"Patching rule: rule_id={rule_id}")

    patch_data: dict = {}
    if name is not None:
        patch_data["name"] = name
    if trigger_condition is not None:
        patch_data["trigger_condition"] = trigger_condition
    if actions is not None:
        patch_data["actions"] = _actions_to_dicts(actions)
    if enabled is not None:
        patch_data["enabled"] = enabled
    if queue_ids is not None:
        patch_data["queues"] = [build_resource_url("queues", qid) for qid in queue_ids]

    if not patch_data:
        return {"error": "No fields provided to update"}

    logger.debug(f"Rule patch payload: {patch_data}")
    updated_rule: Rule = await client.update_part_rule(rule_id, patch_data)
    logger.info(f"Successfully patched rule: id={updated_rule.id}")
    return updated_rule


async def _delete_rule(client: AsyncRossumAPIClient, rule_id: int) -> dict:
    return await delete_resource("rule", rule_id, client.delete_rule)


def register_rule_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    @mcp.tool(description="Retrieve rule details.")
    async def get_rule(rule_id: int) -> Rule:
        return await _get_rule(client, rule_id)

    @mcp.tool(description="List all rules.")
    async def list_rules(
        schema_id: int | None = None, organization_id: int | None = None, enabled: bool | None = None
    ) -> list[Rule]:
        return await _list_rules(client, schema_id, organization_id, enabled)

    @mcp.tool(
        description="Create a rule: trigger is a TxScript condition; action includes id, type, event, payload. Scope with schema_id and/or queue_ids (at least one required)."
    )
    async def create_rule(
        name: str,
        trigger_condition: str,
        actions: list[RuleAction],
        enabled: bool = True,
        schema_id: int | None = None,
        queue_ids: list[int] | None = None,
    ) -> Rule | dict:
        return await _create_rule(client, name, trigger_condition, actions, enabled, schema_id, queue_ids)

    @mcp.tool(description="Replace a rule (PUT); all fields required. Use patch_rule for partial changes.")
    async def update_rule(
        rule_id: int,
        name: str,
        trigger_condition: str,
        actions: list[RuleAction],
        enabled: bool,
        queue_ids: list[int],
    ) -> Rule | dict:
        return await _update_rule(client, rule_id, name, trigger_condition, actions, enabled, queue_ids)

    @mcp.tool(description="Patch a rule (PATCH); only provided fields change. queue_ids=[] clears queue scoping.")
    async def patch_rule(
        rule_id: int,
        name: str | None = None,
        trigger_condition: str | None = None,
        actions: list[RuleAction] | None = None,
        enabled: bool | None = None,
        queue_ids: list[int] | None = None,
    ) -> Rule | dict:
        return await _patch_rule(client, rule_id, name, trigger_condition, actions, enabled, queue_ids)

    @mcp.tool(description="Delete a rule.")
    async def delete_rule(rule_id: int) -> dict:
        return await _delete_rule(client, rule_id)
