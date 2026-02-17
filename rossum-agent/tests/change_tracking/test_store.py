"""Tests for rossum_agent.change_tracking.store module."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from rossum_agent.change_tracking.models import ConfigCommit, EntityChange
from rossum_agent.change_tracking.store import DEFAULT_COMMIT_TTL_SECONDS, CommitStore


def _make_change(**overrides) -> EntityChange:
    defaults = {
        "entity_type": "schema",
        "entity_id": "100",
        "entity_name": "Invoice",
        "operation": "update",
        "before": {"fields": []},
        "after": {"fields": [{"name": "total"}]},
    }
    defaults.update(overrides)
    return EntityChange(**defaults)


def _make_commit(**overrides) -> ConfigCommit:
    defaults = {
        "hash": "abc123def456",
        "parent": None,
        "chat_id": "chat_20250213",
        "timestamp": datetime(2025, 2, 13, 12, 0, 0, tzinfo=UTC),
        "message": "Updated schema fields",
        "user_request": "Add a new field",
        "environment": "https://example.rossum.app/api/v1",
        "changes": [_make_change()],
    }
    defaults.update(overrides)
    return ConfigCommit(**defaults)


def _make_mock_client() -> MagicMock:
    client = MagicMock()
    client.pipeline.return_value = MagicMock()
    return client


class TestCommitStoreSaveAndGet:
    """Test save_commit and get_commit roundtrip."""

    def test_save_commit(self):
        client = _make_mock_client()
        store = CommitStore(client)
        commit = _make_commit()

        store.save_commit(commit)

        pipe = client.pipeline.return_value
        pipe.setex.assert_any_call(
            f"config_commit:{commit.environment}:{commit.hash}",
            DEFAULT_COMMIT_TTL_SECONDS,
            commit.model_dump_json(),
        )
        pipe.zadd.assert_called_once_with(
            f"config_commits:{commit.environment}",
            {commit.hash: commit.timestamp.timestamp()},
        )
        pipe.expire.assert_called_once_with(
            f"config_commits:{commit.environment}",
            DEFAULT_COMMIT_TTL_SECONDS,
        )
        pipe.setex.assert_any_call(
            f"config_commit_latest:{commit.environment}",
            DEFAULT_COMMIT_TTL_SECONDS,
            commit.hash,
        )
        pipe.execute.assert_called_once()

    def test_get_commit_roundtrip(self):
        client = _make_mock_client()
        store = CommitStore(client)
        commit = _make_commit()
        env = commit.environment

        client.get.return_value = commit.model_dump_json().encode()

        result = store.get_commit(env, commit.hash)

        assert result is not None
        assert result.hash == commit.hash
        assert result.parent == commit.parent
        assert result.chat_id == commit.chat_id
        assert result.timestamp == commit.timestamp
        assert result.message == commit.message
        assert result.environment == commit.environment
        assert len(result.changes) == 1
        assert result.changes[0].entity_type == "schema"

    def test_get_commit_not_found(self):
        client = _make_mock_client()
        store = CommitStore(client)

        client.get.return_value = None

        result = store.get_commit("https://example.rossum.app/api/v1", "nonexistent")
        assert result is None


class TestCommitStoreGetLatestHash:
    """Test get_latest_hash."""

    def test_get_latest_hash(self):
        client = _make_mock_client()
        store = CommitStore(client)

        client.get.return_value = b"abc123def456"

        result = store.get_latest_hash("https://example.rossum.app/api/v1")
        assert result == "abc123def456"
        client.get.assert_called_once_with("config_commit_latest:https://example.rossum.app/api/v1")

    def test_get_latest_hash_none(self):
        client = _make_mock_client()
        store = CommitStore(client)

        client.get.return_value = None

        result = store.get_latest_hash("https://example.rossum.app/api/v1")
        assert result is None

    def test_get_latest_hash_string_response(self):
        client = _make_mock_client()
        store = CommitStore(client)

        client.get.return_value = "abc123def456"

        result = store.get_latest_hash("https://example.rossum.app/api/v1")
        assert result == "abc123def456"


class TestCommitStoreListCommits:
    """Test list_commits."""

    def test_list_commits_reverse_chronological(self):
        client = _make_mock_client()
        store = CommitStore(client)
        env = "https://example.rossum.app/api/v1"

        commit_old = _make_commit(
            hash="old_hash",
            timestamp=datetime(2025, 2, 12, 10, 0, 0, tzinfo=UTC),
            message="Old commit",
        )
        commit_new = _make_commit(
            hash="new_hash",
            timestamp=datetime(2025, 2, 13, 12, 0, 0, tzinfo=UTC),
            message="New commit",
        )

        # zrevrange returns newest first
        client.zrevrange.return_value = [b"new_hash", b"old_hash"]

        def get_side_effect(key):
            if key == f"config_commit:{env}:new_hash":
                return commit_new.model_dump_json().encode()
            if key == f"config_commit:{env}:old_hash":
                return commit_old.model_dump_json().encode()
            return None

        client.get.side_effect = get_side_effect

        result = store.list_commits(env)

        assert len(result) == 2
        assert result[0].hash == "new_hash"
        assert result[1].hash == "old_hash"
        client.zrevrange.assert_called_once_with(f"config_commits:{env}", 0, 9)

    def test_list_commits_with_limit(self):
        client = _make_mock_client()
        store = CommitStore(client)
        env = "https://example.rossum.app/api/v1"

        commit = _make_commit(hash="only_hash")
        client.zrevrange.return_value = [b"only_hash"]
        client.get.return_value = commit.model_dump_json().encode()

        result = store.list_commits(env, limit=1)

        assert len(result) == 1
        client.zrevrange.assert_called_once_with(f"config_commits:{env}", 0, 0)

    def test_list_commits_empty(self):
        client = _make_mock_client()
        store = CommitStore(client)

        client.zrevrange.return_value = []

        result = store.list_commits("https://example.rossum.app/api/v1")
        assert result == []

    def test_list_commits_skips_missing(self):
        client = _make_mock_client()
        store = CommitStore(client)
        env = "https://example.rossum.app/api/v1"

        commit = _make_commit(hash="existing")
        client.zrevrange.return_value = [b"existing", b"expired"]

        def get_side_effect(key):
            if key == f"config_commit:{env}:existing":
                return commit.model_dump_json().encode()
            return None

        client.get.side_effect = get_side_effect

        result = store.list_commits(env)

        assert len(result) == 1
        assert result[0].hash == "existing"

    def test_list_commits_string_hashes(self):
        client = _make_mock_client()
        store = CommitStore(client)
        env = "https://example.rossum.app/api/v1"

        commit = _make_commit(hash="str_hash")
        # Some Redis clients may return strings instead of bytes
        client.zrevrange.return_value = ["str_hash"]
        client.get.return_value = commit.model_dump_json().encode()

        result = store.list_commits(env)

        assert len(result) == 1
        assert result[0].hash == "str_hash"


class TestCommitStoreCustomTTL:
    """Test custom TTL configuration."""

    def test_custom_ttl(self):
        client = _make_mock_client()
        custom_ttl = 7 * 24 * 3600  # 7 days
        store = CommitStore(client, ttl_seconds=custom_ttl)
        commit = _make_commit()

        store.save_commit(commit)

        pipe = client.pipeline.return_value
        pipe.setex.assert_any_call(
            f"config_commit:{commit.environment}:{commit.hash}",
            custom_ttl,
            commit.model_dump_json(),
        )
