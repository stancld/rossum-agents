"""Tests for rossum_agent.change_tracking.models module."""

from __future__ import annotations

from datetime import UTC, datetime

from rossum_agent.change_tracking.models import (
    ConfigCommit,
    EntityChange,
    compute_commit_hash,
)


class TestEntityChange:
    """Test EntityChange model."""

    def test_create_operation(self):
        change = EntityChange(
            entity_type="schema",
            entity_id="123",
            entity_name="Invoice Schema",
            operation="create",
            before=None,
            after={"name": "Invoice Schema"},
        )
        assert change.entity_type == "schema"
        assert change.entity_id == "123"
        assert change.entity_name == "Invoice Schema"
        assert change.operation == "create"
        assert change.before is None
        assert change.after == {"name": "Invoice Schema"}

    def test_update_operation(self):
        change = EntityChange(
            entity_type="queue",
            entity_id="456",
            entity_name="Main Queue",
            operation="update",
            before={"name": "Old Queue"},
            after={"name": "Main Queue"},
        )
        assert change.operation == "update"
        assert change.before == {"name": "Old Queue"}
        assert change.after == {"name": "Main Queue"}

    def test_delete_operation(self):
        change = EntityChange(
            entity_type="hook",
            entity_id="789",
            entity_name="Webhook",
            operation="delete",
            before={"name": "Webhook"},
            after=None,
        )
        assert change.operation == "delete"
        assert change.before == {"name": "Webhook"}
        assert change.after is None


class TestConfigCommit:
    """Test ConfigCommit model."""

    def _make_commit(self, **overrides) -> ConfigCommit:
        defaults = {
            "hash": "abc123def456",
            "parent": None,
            "chat_id": "chat_20250213",
            "timestamp": datetime(2025, 2, 13, 12, 0, 0, tzinfo=UTC),
            "message": "Updated schema fields",
            "user_request": "Add a new field to the schema",
            "environment": "https://example.rossum.app/api/v1",
            "changes": [
                EntityChange(
                    entity_type="schema",
                    entity_id="100",
                    entity_name="Invoice",
                    operation="update",
                    before={"fields": []},
                    after={"fields": [{"name": "total"}]},
                )
            ],
        }
        defaults.update(overrides)
        return ConfigCommit(**defaults)

    def test_model_dump(self):
        commit = self._make_commit()
        result = commit.model_dump(mode="json")

        assert result["hash"] == "abc123def456"
        assert result["parent"] is None
        assert result["chat_id"] == "chat_20250213"
        assert result["timestamp"] == "2025-02-13T12:00:00Z"
        assert result["message"] == "Updated schema fields"
        assert result["user_request"] == "Add a new field to the schema"
        assert result["environment"] == "https://example.rossum.app/api/v1"
        assert len(result["changes"]) == 1
        assert result["changes"][0]["entity_type"] == "schema"
        assert result["changes"][0]["operation"] == "update"

    def test_model_validate(self):
        data = {
            "hash": "abc123def456",
            "parent": "prev_hash",
            "chat_id": "chat_20250213",
            "timestamp": "2025-02-13T12:00:00+00:00",
            "message": "Updated schema fields",
            "user_request": "Add a new field to the schema",
            "environment": "https://example.rossum.app/api/v1",
            "changes": [
                {
                    "entity_type": "schema",
                    "entity_id": "100",
                    "entity_name": "Invoice",
                    "operation": "update",
                    "before": {"fields": []},
                    "after": {"fields": [{"name": "total"}]},
                }
            ],
        }
        commit = ConfigCommit.model_validate(data)

        assert commit.hash == "abc123def456"
        assert commit.parent == "prev_hash"
        assert commit.chat_id == "chat_20250213"
        assert commit.timestamp == datetime(2025, 2, 13, 12, 0, 0, tzinfo=UTC)
        assert commit.message == "Updated schema fields"
        assert len(commit.changes) == 1
        assert commit.changes[0].entity_type == "schema"

    def test_roundtrip(self):
        original = self._make_commit(parent="parent_hash")
        data = original.model_dump(mode="json")
        restored = ConfigCommit.model_validate(data)

        assert restored.hash == original.hash
        assert restored.parent == original.parent
        assert restored.chat_id == original.chat_id
        assert restored.timestamp == original.timestamp
        assert restored.message == original.message
        assert restored.user_request == original.user_request
        assert restored.environment == original.environment
        assert len(restored.changes) == len(original.changes)
        assert restored.changes[0].entity_type == original.changes[0].entity_type
        assert restored.changes[0].entity_id == original.changes[0].entity_id
        assert restored.changes[0].operation == original.changes[0].operation
        assert restored.changes[0].before == original.changes[0].before
        assert restored.changes[0].after == original.changes[0].after

    def test_model_validate_with_no_changes(self):
        data = {
            "hash": "abc123",
            "chat_id": "chat_1",
            "timestamp": "2025-02-13T12:00:00+00:00",
            "message": "Empty commit",
            "user_request": "Do nothing",
            "environment": "https://example.rossum.app/api/v1",
        }
        commit = ConfigCommit.model_validate(data)
        assert commit.changes == []
        assert commit.parent is None


class TestComputeCommitHash:
    """Test compute_commit_hash function."""

    def test_consistent_hash(self):
        ts = datetime(2025, 2, 13, 12, 0, 0, tzinfo=UTC)
        changes = [
            EntityChange(
                entity_type="schema",
                entity_id="100",
                entity_name="Invoice",
                operation="update",
                before={"fields": []},
                after={"fields": [{"name": "total"}]},
            )
        ]
        hash1 = compute_commit_hash(changes, ts)
        hash2 = compute_commit_hash(changes, ts)
        assert hash1 == hash2

    def test_hash_length(self):
        ts = datetime(2025, 2, 13, 12, 0, 0, tzinfo=UTC)
        changes = [
            EntityChange(
                entity_type="schema",
                entity_id="100",
                entity_name="Invoice",
                operation="create",
                before=None,
                after={"name": "Invoice"},
            )
        ]
        result = compute_commit_hash(changes, ts)
        assert len(result) == 12

    def test_different_changes_produce_different_hashes(self):
        ts = datetime(2025, 2, 13, 12, 0, 0, tzinfo=UTC)
        changes_a = [
            EntityChange(
                entity_type="schema",
                entity_id="100",
                entity_name="Invoice",
                operation="create",
                before=None,
                after={"name": "Invoice"},
            )
        ]
        changes_b = [
            EntityChange(
                entity_type="queue",
                entity_id="200",
                entity_name="Main Queue",
                operation="delete",
                before={"name": "Main Queue"},
                after=None,
            )
        ]
        assert compute_commit_hash(changes_a, ts) != compute_commit_hash(changes_b, ts)

    def test_different_timestamps_produce_different_hashes(self):
        changes = [
            EntityChange(
                entity_type="schema",
                entity_id="100",
                entity_name="Invoice",
                operation="update",
                before={"fields": []},
                after={"fields": [{"name": "total"}]},
            )
        ]
        ts_a = datetime(2025, 2, 13, 12, 0, 0, tzinfo=UTC)
        ts_b = datetime(2025, 2, 13, 13, 0, 0, tzinfo=UTC)
        assert compute_commit_hash(changes, ts_a) != compute_commit_hash(changes, ts_b)

    def test_empty_changes(self):
        ts = datetime(2025, 2, 13, 12, 0, 0, tzinfo=UTC)
        result = compute_commit_hash([], ts)
        assert len(result) == 12
        assert result == compute_commit_hash([], ts)
