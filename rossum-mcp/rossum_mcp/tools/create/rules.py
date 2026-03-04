"""Create operations for rules."""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import TYPE_CHECKING

from rossum_api.models.rule import Rule, RuleAction

from rossum_mcp.tools.base import build_resource_url

if TYPE_CHECKING:
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


def _actions_to_dicts(actions: list[RuleAction]) -> list[dict]:
    """Serialize actions for API payloads, handling both dataclass instances and raw dicts."""
    return [asdict(a) if isinstance(a, RuleAction) else a for a in actions]


async def _create_rule(
    client: AsyncRossumAPIClient,
    name: str,
    trigger_condition: str,
    actions: list[RuleAction],
    enabled: bool = True,
    schema_id: int | None = None,
    queue_ids: list[int] | None = None,
) -> Rule | dict:
    if schema_id is None and not queue_ids:
        return {"error": "Provide at least one of schema_id or queue_ids to scope the rule."}

    logger.debug(f"Creating rule: name={name}, schema_id={schema_id}, enabled={enabled}")

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

    rule: Rule = await client.create_new_rule(rule_data)
    logger.info(f"Rule {rule.id} '{rule.name}' created")
    return rule
