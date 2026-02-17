from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class EntityChange(BaseModel):
    entity_type: str  # queue, schema, hook, rule, ...
    entity_id: str
    entity_name: str
    operation: Literal["create", "update", "delete"]
    before: dict | None  # None for creates
    after: dict | None  # None for deletes


class ConfigCommit(BaseModel):
    hash: str  # SHA-256 of serialized changes
    parent: str | None = None  # Previous commit hash for this environment
    chat_id: str
    timestamp: datetime
    message: str  # LLM-generated summary
    user_request: str  # Original user prompt
    environment: str  # "{base_url}" identifier
    changes: list[EntityChange] = Field(default_factory=list)


def compute_commit_hash(changes: list[EntityChange], timestamp: datetime) -> str:
    """Compute SHA-256 hash of serialized changes and timestamp."""
    serialized = json.dumps(
        {
            "timestamp": timestamp.isoformat(),
            "changes": [
                {
                    "entity_type": c.entity_type,
                    "entity_id": c.entity_id,
                    "operation": c.operation,
                    "before": c.before,
                    "after": c.after,
                }
                for c in changes
            ],
        },
        sort_keys=True,
    )
    return hashlib.sha256(serialized.encode()).hexdigest()[:12]
