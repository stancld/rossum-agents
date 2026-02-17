"""Agent tools for querying and managing configuration change history."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

from anthropic import beta_tool
from rossum_api import AsyncRossumAPIClient
from rossum_api.domain_logic.resources import Resource
from rossum_api.dtos import Token
from rossum_mcp.tools.schemas.validation import sanitize_schema_content

from rossum_agent.change_tracking.models import EntityChange
from rossum_agent.rossum_mcp_integration import unwrap
from rossum_agent.tools.core import (
    get_commit_store,
    get_mcp_connection,
    get_mcp_event_loop,
    get_rossum_credentials,
    get_rossum_environment,
)

if TYPE_CHECKING:
    from typing import Literal

logger = logging.getLogger(__name__)

# Entity types that can be reverted programmatically via rossum_api
_ENTITY_TYPE_TO_RESOURCE: dict[str, Resource] = {
    "schema": Resource.Schema,
    "queue": Resource.Queue,
    "hook": Resource.Hook,
    "rule": Resource.Rule,
    "inbox": Resource.Inbox,
    "workspace": Resource.Workspace,
    "connector": Resource.Connector,
    "email_template": Resource.EmailTemplate,
}

# SDK method names for recreating deleted entities
_ENTITY_TYPE_TO_CREATE_METHOD: dict[str, str] = {
    "schema": "create_new_schema",
    "queue": "create_new_queue",
    "hook": "create_new_hook",
    "rule": "create_new_rule",
    "inbox": "create_new_inbox",
    "workspace": "create_new_workspace",
    "connector": "create_new_connector",
    "email_template": "create_new_email_template",
}

# SDK method names for deleting created entities
_ENTITY_TYPE_TO_DELETE_METHOD: dict[str, str] = {
    "schema": "delete_schema",
    "queue": "delete_queue",
    "hook": "delete_hook",
    "rule": "delete_rule",
    "workspace": "delete_workspace",
}

# Fields that are read-only and should never be included in a revert PATCH
_READ_ONLY_FIELDS = frozenset(
    {
        "url",
        "id",
        "organization",
        "created_at",
        "modified_at",
        "modified_by",
        "created_by",
    }
)


def _flush_pending_changes() -> None:
    """Commit any pending tracked changes to the store.

    Called before reading history or reverting so the agent can see
    changes made earlier in the same run.
    """
    mcp_connection = get_mcp_connection()
    if not mcp_connection or not mcp_connection.has_changes():
        return

    mcp_connection.flush_and_commit("auto-flush before history query")


def _compute_revert_patch(before: dict, after: dict) -> dict:
    """Compute the minimal PATCH payload to revert after→before.

    Returns only fields that differ between before and after,
    excluding read-only fields.
    """
    before_inner = unwrap(before)
    after_inner = unwrap(after)
    patch: dict = {}
    for key, before_val in before_inner.items():
        if key in _READ_ONLY_FIELDS:
            continue
        if after_inner.get(key) != before_val:
            patch[key] = before_val
    return patch


async def _revert_entity_update(api_base_url: str, token: str, change: EntityChange) -> dict:
    """Revert an entity update by patching changed fields back to the before state."""
    entity_id = int(change.entity_id)
    resource = _ENTITY_TYPE_TO_RESOURCE[change.entity_type]

    if not isinstance(change.before, dict) or not isinstance(change.after, dict):
        msg = f"Cannot revert {change.entity_type} {entity_id}: missing before/after snapshot"
        raise ValueError(msg)

    if change.entity_type == "schema":
        before_inner = unwrap(change.before)
        content = before_inner.get("content")
        if not isinstance(content, list):
            msg = f"Cannot revert schema {entity_id}: 'before' snapshot has no content"
            raise ValueError(msg)
        patch = {"content": sanitize_schema_content(content)}
    else:
        patch = _compute_revert_patch(change.before, change.after)

    if not patch:
        return {"status": "no_changes", "entity_type": change.entity_type, "entity_id": change.entity_id}

    client = AsyncRossumAPIClient(base_url=api_base_url, credentials=Token(token=token))
    await client._http_client.update(resource, entity_id, patch)
    return {"status": "reverted", "entity_type": change.entity_type, "entity_id": change.entity_id}


async def _revert_entity_delete(api_base_url: str, token: str, change: EntityChange) -> dict:
    """Revert an entity deletion by recreating it from the before snapshot."""
    create_method = _ENTITY_TYPE_TO_CREATE_METHOD[change.entity_type]

    if not isinstance(change.before, dict):
        msg = f"Cannot recreate {change.entity_type} {change.entity_id}: missing before snapshot"
        raise ValueError(msg)

    data = unwrap(change.before)
    cleaned = {k: v for k, v in data.items() if k not in _READ_ONLY_FIELDS}

    client = AsyncRossumAPIClient(base_url=api_base_url, credentials=Token(token=token))
    result = await getattr(client, create_method)(cleaned)
    new_id = getattr(result, "id", None)
    return {
        "status": "recreated",
        "entity_type": change.entity_type,
        "entity_id": change.entity_id,
        "new_entity_id": str(new_id) if new_id is not None else None,
    }


async def _revert_entity_create(api_base_url: str, token: str, change: EntityChange) -> dict:
    """Revert an entity creation by deleting it."""
    delete_method = _ENTITY_TYPE_TO_DELETE_METHOD[change.entity_type]
    entity_id = int(change.entity_id)

    client = AsyncRossumAPIClient(base_url=api_base_url, credentials=Token(token=token))
    await getattr(client, delete_method)(entity_id)
    return {"status": "deleted", "entity_type": change.entity_type, "entity_id": change.entity_id}


@beta_tool
def show_change_history(limit: int = 10) -> str:
    """Show recent configuration changes made by the agent.

    Args:
        limit: Maximum number of commits to show (default 10).

    Returns:
        JSON list of recent commits with hash, message, timestamp, and change count.
    """
    store = get_commit_store()
    environment = get_rossum_environment()
    if store is None or environment is None:
        return json.dumps({"error": "Change tracking not available"})

    _flush_pending_changes()

    commits = store.list_commits(environment, limit=limit)
    if not commits:
        return json.dumps({"message": "No configuration changes recorded"})

    return json.dumps(
        [
            {
                "hash": c.hash,
                "message": c.message,
                "timestamp": c.timestamp.isoformat(),
                "changes": len(c.changes),
                "user_request": c.user_request[:100],
            }
            for c in commits
        ]
    )


@beta_tool
def show_commit_details(commit_hash: str) -> str:
    """Show full details and diffs for a specific configuration commit.

    Args:
        commit_hash: The hash of the commit to inspect.

    Returns:
        JSON with commit metadata and before/after snapshots for each change.
    """
    store = get_commit_store()
    environment = get_rossum_environment()
    if store is None or environment is None:
        return json.dumps({"error": "Change tracking not available"})

    commit = store.get_commit(environment, commit_hash)
    if commit is None:
        return json.dumps({"error": f"Commit {commit_hash} not found"})

    return json.dumps(
        {
            "hash": commit.hash,
            "message": commit.message,
            "timestamp": commit.timestamp.isoformat(),
            "user_request": commit.user_request,
            "parent": commit.parent,
            "changes": [c.model_dump() for c in commit.changes],
        }
    )


def _can_direct_revert(change: EntityChange) -> bool:
    """Check if a change can be reverted programmatically."""
    if change.operation == "update":
        return change.entity_type in _ENTITY_TYPE_TO_RESOURCE and change.before is not None
    if change.operation == "delete":
        return change.entity_type in _ENTITY_TYPE_TO_CREATE_METHOD and change.before is not None
    if change.operation == "create":
        return change.entity_type in _ENTITY_TYPE_TO_DELETE_METHOD
    return False


def _build_plan_action(change: EntityChange) -> dict | None:
    """Build a plan-based revert action for changes that can't be reverted programmatically."""
    if change.operation == "create":
        return {
            "action": "delete",
            "entity_type": change.entity_type,
            "entity_id": change.entity_id,
            "entity_name": change.entity_name,
            "tool": f"delete_{change.entity_type}",
            "args": {f"{change.entity_type}_id": change.entity_id},
        }
    if change.operation == "delete" and change.before:
        return {
            "action": "recreate",
            "entity_type": change.entity_type,
            "entity_id": change.entity_id,
            "entity_name": change.entity_name,
            "tool": f"create_{change.entity_type}",
            "original_data": change.before,
        }
    if change.operation == "update" and change.before:
        return {
            "action": "restore",
            "entity_type": change.entity_type,
            "entity_id": change.entity_id,
            "entity_name": change.entity_name,
            "tool": f"update_{change.entity_type}",
            "restore_to": change.before,
        }
    return None


def _collapsed_operation(
    first: Literal["create", "update", "delete"],
    last: Literal["create", "update", "delete"],
) -> Literal["create", "update", "delete"]:
    """Derive the net operation from a sequence of operations on the same entity."""
    if first == last:
        return first
    if first == "create":
        # create → update = still a create; create → delete = no-op (handled later)
        return "create" if last == "update" else "delete"
    if first == "update" and last == "delete":
        return "delete"
    # update → create or delete → * are unusual but default to last
    return last


def _deduplicate_changes(changes: list[EntityChange]) -> list[EntityChange]:
    """Collapse multiple changes to the same entity into one.

    When an entity is modified multiple times in a single commit (e.g. prune
    then patch), only the first "before" snapshot represents the pre-commit
    state. We keep first-seen before + last-seen after, and derive the net
    operation from the sequence.

    Safety net: if an entity was created then deleted in the same commit
    (before=None, after=None), it's a no-op and is dropped entirely.
    """
    seen: dict[tuple[str, str], int] = {}
    result: list[EntityChange] = []
    for change in changes:
        key = (change.entity_type, change.entity_id)
        if key in seen:
            idx = seen[key]
            existing = result[idx]
            result[idx] = EntityChange(
                entity_type=change.entity_type,
                entity_id=change.entity_id,
                entity_name=change.entity_name or existing.entity_name,
                operation=_collapsed_operation(existing.operation, change.operation),
                before=existing.before,
                after=change.after,
            )
        else:
            seen[key] = len(result)
            result.append(change)

    # Drop no-ops: entity created and then deleted → net effect is nothing
    return [c for c in result if c.before is not None or c.after is not None]


@beta_tool
def revert_commit(commit_hash: str) -> str:
    """Revert the most recent configuration commit by applying inverse operations.

    Updates, creates, and deletes of known entity types are reverted programmatically
    when SDK methods are available. Unsupported operations produce a revert plan for
    the agent to execute.

    Args:
        commit_hash: Hash of the commit to revert (must be the latest).

    Returns:
        JSON with revert results (executed reverts and remaining plan actions).
    """
    store = get_commit_store()
    environment = get_rossum_environment()
    if store is None or environment is None:
        return json.dumps({"error": "Change tracking not available"})

    _flush_pending_changes()

    if (latest_hash := store.get_latest_hash(environment)) != commit_hash:
        return json.dumps(
            {"error": f"Can only revert the latest commit. Latest is {latest_hash}, requested {commit_hash}"}
        )

    if (commit := store.get_commit(environment, commit_hash)) is None:
        return json.dumps({"error": f"Commit {commit_hash} not found"})

    credentials = get_rossum_credentials()
    loop = get_mcp_event_loop()

    # Deduplicate: for each entity, keep only the earliest "before" and latest operation
    deduped = _deduplicate_changes(commit.changes)

    executed: list[dict] = []
    plan_actions: list[dict] = []
    errors: list[dict] = []

    for change in deduped:
        if _can_direct_revert(change) and credentials and loop:
            api_base_url, token = credentials
            try:
                if change.operation == "update":
                    coro = _revert_entity_update(api_base_url, token, change)
                elif change.operation == "delete":
                    coro = _revert_entity_delete(api_base_url, token, change)
                else:
                    coro = _revert_entity_create(api_base_url, token, change)
                result = asyncio.run_coroutine_threadsafe(coro, loop).result()
                executed.append(result)
            except Exception as e:
                logger.exception(f"Failed to revert {change.entity_type}:{change.entity_id}")
                errors.append(
                    {
                        "entity_type": change.entity_type,
                        "entity_id": change.entity_id,
                        "error": str(e),
                    }
                )
        else:
            if action := _build_plan_action(change):
                plan_actions.append(action)

    response: dict = {
        "status": "completed" if not plan_actions and not errors else "partial",
        "commit_hash": commit_hash,
        "message": f"Reverting: {commit.message}",
        "executed": executed,
    }
    if errors:
        response["errors"] = errors
    if plan_actions:
        response["remaining_actions"] = plan_actions
        response["instructions"] = "Execute each remaining action above using the specified MCP tools."

    return json.dumps(response)
