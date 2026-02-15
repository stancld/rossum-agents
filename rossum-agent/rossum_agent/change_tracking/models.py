from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Literal


@dataclass
class EntityChange:
    entity_type: str  # queue, schema, hook, rule, ...
    entity_id: str
    entity_name: str
    operation: Literal["create", "update", "delete"]
    before: dict | None  # None for creates
    after: dict | None  # None for deletes


@dataclass
class ConfigCommit:
    hash: str  # SHA-256 of serialized changes
    parent: str | None  # Previous commit hash for this environment
    chat_id: str
    timestamp: datetime
    message: str  # LLM-generated summary
    user_request: str  # Original user prompt
    environment: str  # "{base_url}" identifier
    changes: list[EntityChange] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "hash": self.hash,
            "parent": self.parent,
            "chat_id": self.chat_id,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
            "user_request": self.user_request,
            "environment": self.environment,
            "changes": [asdict(c) for c in self.changes],
        }

    @classmethod
    def from_dict(cls, data: dict) -> ConfigCommit:
        return cls(
            hash=data["hash"],
            parent=data.get("parent"),
            chat_id=data["chat_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            message=data["message"],
            user_request=data["user_request"],
            environment=data["environment"],
            changes=[
                EntityChange(
                    entity_type=c["entity_type"],
                    entity_id=c["entity_id"],
                    entity_name=c["entity_name"],
                    operation=c["operation"],
                    before=c.get("before"),
                    after=c.get("after"),
                )
                for c in data.get("changes", [])
            ],
        )


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
