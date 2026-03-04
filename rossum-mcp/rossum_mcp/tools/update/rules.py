"""Update operations for rules."""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import TYPE_CHECKING

from rossum_api.domain_logic.resources import Resource
from rossum_api.models.rule import Rule, RuleAction

from rossum_mcp.tools.base import build_resource_url


def _actions_to_dicts(actions: list[RuleAction]) -> list[dict]:
    """Serialize actions for API payloads, handling both dataclass instances and raw dicts."""
    return [asdict(a) if isinstance(a, RuleAction) else a for a in actions]


if TYPE_CHECKING:
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


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
    logger.debug(f"Updating rule: rule_id={rule_id}, name={name}")
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

    await client._http_client.update(Resource.Rule, rule_id, rule_data)
    updated_rule: Rule = await client.retrieve_rule(rule_id)
    logger.info(f"Rule {updated_rule.id} updated")
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
    logger.debug(f"Patching rule: rule_id={rule_id}")

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

    updated_rule: Rule = await client.update_part_rule(rule_id, patch_data)
    logger.info(f"Rule {updated_rule.id} patched")
    return updated_rule
