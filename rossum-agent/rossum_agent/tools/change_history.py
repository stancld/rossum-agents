"""Agent tools for querying and managing configuration change history."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict
from typing import TYPE_CHECKING

from anthropic import beta_tool
from rossum_api import AsyncRossumAPIClient
from rossum_api.domain_logic.resources import Resource
from rossum_api.dtos import Token
from rossum_mcp.tools.schemas.validation import sanitize_schema_content

from rossum_agent.change_tracking.commit_service import CommitService
from rossum_agent.change_tracking.models import EntityChange
from rossum_agent.rossum_mcp_integration import _unwrap
from rossum_agent.tools.core import (
    get_commit_store,
    get_mcp_connection,
    get_mcp_event_loop,
    get_rossum_credentials,
    get_rossum_environment,
)

if TYPE_CHECKING:
    from rossum_agent.change_tracking.store import CommitStore

logger = logging.getLogger(__name__)

# Entity types where we can programmatically revert updates via rossum_api
_DIRECT_REVERT_ENTITY_TYPES = {"schema"}


def _flush_pending_changes(store: CommitStore, environment: str) -> None:
    """Commit any pending tracked changes to the store.

    Called before reading history or reverting so the agent can see
    changes made earlier in the same run.
    """
    mcp_connection = get_mcp_connection()
    if not mcp_connection or not mcp_connection.has_changes():
        return

    chat_id = mcp_connection.chat_id or "unknown"
    service = CommitService(store)
    service.create_commit(mcp_connection, chat_id, "", environment)


async def _revert_schema_update(api_base_url: str, token: str, change: EntityChange) -> dict:
    """Revert a schema update by patching only the content field."""
    schema_id = int(change.entity_id)
    data = change.before
    if not isinstance(data, dict):
        msg = f"Cannot revert schema {schema_id}: no 'before' snapshot"
        raise ValueError(msg)
    data = _unwrap(data)
    content = data.get("content")
    if not isinstance(content, list):
        msg = f"Cannot revert schema {schema_id}: 'before' snapshot has no content"
        raise ValueError(msg)
    sanitized = sanitize_schema_content(content)
    client = AsyncRossumAPIClient(base_url=api_base_url, credentials=Token(token=token))
    await client._http_client.update(Resource.Schema, schema_id, {"content": sanitized})
    return {"status": "reverted", "entity_type": "schema", "entity_id": change.entity_id}


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

    _flush_pending_changes(store, environment)

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
            "changes": [asdict(c) for c in commit.changes],
        }
    )


def _can_direct_revert(change: EntityChange) -> bool:
    """Check if a change can be reverted programmatically."""
    return (
        change.operation == "update"
        and change.entity_type in _DIRECT_REVERT_ENTITY_TYPES
        and change.before is not None
    )


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


def _deduplicate_changes(changes: list[EntityChange]) -> list[EntityChange]:
    """Collapse multiple changes to the same entity into one.

    When an entity is modified multiple times in a single commit (e.g. prune
    then patch), only the first "before" snapshot represents the pre-commit
    state. We keep first-seen before + last-seen after.

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
                operation=existing.operation,
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

    Schema updates are reverted programmatically. Other entity types produce a
    revert plan for the agent to execute.

    Args:
        commit_hash: Hash of the commit to revert (must be the latest).

    Returns:
        JSON with revert results (executed reverts and remaining plan actions).
    """
    store = get_commit_store()
    environment = get_rossum_environment()
    if store is None or environment is None:
        return json.dumps({"error": "Change tracking not available"})

    _flush_pending_changes(store, environment)

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
                result = asyncio.run_coroutine_threadsafe(
                    _revert_schema_update(api_base_url, token, change), loop
                ).result()
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
