"""Tests for rossum_agent.change_tracking.commit_service module."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from rossum_agent.change_tracking.commit_service import (
    CommitService,
    _fallback_commit_message,
    _format_changes_for_message,
    generate_commit_message,
)
from rossum_agent.change_tracking.models import EntityChange


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


class TestCreateCommit:
    def test_create_commit_no_changes(self):
        store = MagicMock()
        tracking_conn = MagicMock()
        tracking_conn.get_changes.return_value = []

        service = CommitService(store, MagicMock())
        result = service.create_commit(
            tracking_conn, chat_id="chat_1", user_request="Do something", environment="https://example.rossum.app"
        )

        assert result is None
        store.save_commit.assert_not_called()

    @patch("rossum_agent.change_tracking.commit_service.generate_commit_message")
    def test_create_commit_with_changes(self, mock_gen_msg):
        mock_gen_msg.return_value = "Update schema 'Invoice'"

        store = MagicMock()
        store.get_latest_hash.return_value = None
        tracking_conn = MagicMock()
        changes = [_make_change()]
        tracking_conn.get_changes.return_value = changes

        service = CommitService(store, MagicMock())
        result = service.create_commit(
            tracking_conn,
            chat_id="chat_1",
            user_request="Add a field",
            environment="https://example.rossum.app",
        )

        assert result is not None
        assert result.message == "Update schema 'Invoice'"
        assert result.chat_id == "chat_1"
        assert result.user_request == "Add a field"
        assert result.environment == "https://example.rossum.app"
        assert result.changes == changes
        store.save_commit.assert_called_once_with(result)

    @patch("rossum_agent.change_tracking.commit_service.generate_commit_message")
    def test_create_commit_sets_parent_hash(self, mock_gen_msg):
        mock_gen_msg.return_value = "Update schema"

        store = MagicMock()
        store.get_latest_hash.return_value = "parent_abc123"
        tracking_conn = MagicMock()
        tracking_conn.get_changes.return_value = [_make_change()]

        service = CommitService(store, MagicMock())
        result = service.create_commit(
            tracking_conn,
            chat_id="chat_1",
            user_request="Add a field",
            environment="https://example.rossum.app",
        )

        assert result is not None
        assert result.parent == "parent_abc123"
        store.get_latest_hash.assert_called_once_with("https://example.rossum.app")

    @patch("rossum_agent.change_tracking.commit_service.generate_commit_message")
    def test_create_commit_clears_tracking_changes(self, mock_gen_msg):
        mock_gen_msg.return_value = "Update schema"

        store = MagicMock()
        store.get_latest_hash.return_value = None
        tracking_conn = MagicMock()
        tracking_conn.get_changes.return_value = [_make_change()]

        service = CommitService(store, MagicMock())
        service.create_commit(
            tracking_conn,
            chat_id="chat_1",
            user_request="Add a field",
            environment="https://example.rossum.app",
        )

        tracking_conn.clear_changes.assert_called_once()


class TestCreateCommitWithSnapshots:
    @patch("rossum_agent.change_tracking.commit_service.generate_commit_message")
    def test_saves_after_snapshot(self, mock_gen_msg):
        mock_gen_msg.return_value = "Update schema"

        commit_store = MagicMock()
        commit_store.get_latest_hash.return_value = None
        snapshot_store = MagicMock()
        snapshot_store.get_earliest_version.return_value = ("existing", 100.0)  # not first change
        tracking_conn = MagicMock()
        after_data = {"fields": [{"name": "total"}]}
        tracking_conn.get_changes.return_value = [_make_change(after=after_data)]

        service = CommitService(commit_store, snapshot_store)
        result = service.create_commit(
            tracking_conn,
            chat_id="chat_1",
            user_request="Add a field",
            environment="https://example.rossum.app",
        )

        assert result is not None
        snapshot_store.save_snapshot.assert_called_once()
        call_args = snapshot_store.save_snapshot.call_args
        assert call_args.args[3] == result.hash
        assert call_args.args[5] == after_data

    @patch("rossum_agent.change_tracking.commit_service.generate_commit_message")
    def test_saves_before_snapshot_for_first_update(self, mock_gen_msg):
        """First update of an entity saves change.before at parent commit hash/timestamp."""
        mock_gen_msg.return_value = "Update schema"

        parent_ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        parent_commit = MagicMock()
        parent_commit.hash = "parent_hash"
        parent_commit.timestamp = parent_ts

        commit_store = MagicMock()
        commit_store.get_latest_hash.return_value = "parent_hash"
        commit_store.get_commit.return_value = parent_commit
        snapshot_store = MagicMock()
        snapshot_store.get_earliest_version.return_value = None  # first change for this entity
        tracking_conn = MagicMock()
        before_data = {"fields": []}
        after_data = {"fields": [{"name": "total"}]}
        tracking_conn.get_changes.return_value = [_make_change(before=before_data, after=after_data)]

        service = CommitService(commit_store, snapshot_store)
        result = service.create_commit(
            tracking_conn,
            chat_id="chat_1",
            user_request="Add a field",
            environment="https://example.rossum.app",
        )

        assert result is not None
        assert snapshot_store.save_snapshot.call_count == 2
        calls = snapshot_store.save_snapshot.call_args_list
        # First call: before-snapshot at parent hash/timestamp
        assert calls[0].args[3] == "parent_hash"
        assert calls[0].args[4] == parent_ts
        assert calls[0].args[5] == before_data
        # Second call: after-snapshot at current commit hash
        assert calls[1].args[3] == result.hash
        assert calls[1].args[5] == after_data

    @patch("rossum_agent.change_tracking.commit_service.generate_commit_message")
    def test_before_snapshot_uses_sentinel_when_no_parent(self, mock_gen_msg):
        """When no parent commit exists, before-snapshot uses 'initial' sentinel."""
        mock_gen_msg.return_value = "Update schema"

        commit_store = MagicMock()
        commit_store.get_latest_hash.return_value = None
        commit_store.get_commit.return_value = None  # no parent commit in store
        snapshot_store = MagicMock()
        snapshot_store.get_earliest_version.return_value = None
        tracking_conn = MagicMock()
        tracking_conn.get_changes.return_value = [
            _make_change(before={"fields": []}, after={"fields": [{"name": "x"}]})
        ]

        service = CommitService(commit_store, snapshot_store)
        service.create_commit(
            tracking_conn,
            chat_id="chat_1",
            user_request="Add a field",
            environment="https://example.rossum.app",
        )

        calls = snapshot_store.save_snapshot.call_args_list
        assert len(calls) == 2
        assert calls[0].args[3] == "initial"

    @patch("rossum_agent.change_tracking.commit_service.generate_commit_message")
    def test_skips_before_snapshot_for_non_first_update(self, mock_gen_msg):
        """Before-snapshot is not saved when the entity already has snapshots."""
        mock_gen_msg.return_value = "Update schema"

        commit_store = MagicMock()
        commit_store.get_latest_hash.return_value = None
        snapshot_store = MagicMock()
        snapshot_store.get_earliest_version.return_value = ("older_hash", 500.0)  # already tracked
        tracking_conn = MagicMock()
        after_data = {"fields": [{"name": "total"}]}
        tracking_conn.get_changes.return_value = [_make_change(after=after_data)]

        service = CommitService(commit_store, snapshot_store)
        result = service.create_commit(
            tracking_conn,
            chat_id="chat_1",
            user_request="Add a field",
            environment="https://example.rossum.app",
        )

        assert result is not None
        snapshot_store.save_snapshot.assert_called_once()  # only after-snapshot

    @patch("rossum_agent.change_tracking.commit_service.generate_commit_message")
    def test_saves_only_after_snapshot_for_create(self, mock_gen_msg):
        """Create operation (before=None) saves only the after-snapshot."""
        mock_gen_msg.return_value = "Create queue"

        commit_store = MagicMock()
        commit_store.get_latest_hash.return_value = None
        snapshot_store = MagicMock()
        tracking_conn = MagicMock()
        after_data = {"id": 42, "name": "New Queue"}
        tracking_conn.get_changes.return_value = [_make_change(operation="create", before=None, after=after_data)]

        service = CommitService(commit_store, snapshot_store)
        result = service.create_commit(
            tracking_conn,
            chat_id="chat_1",
            user_request="Create a queue",
            environment="https://example.rossum.app",
        )

        assert result is not None
        snapshot_store.save_snapshot.assert_called_once()
        call_args = snapshot_store.save_snapshot.call_args
        assert call_args.args[3] == result.hash
        assert call_args.args[5] == after_data

    @patch("rossum_agent.change_tracking.commit_service.generate_commit_message")
    def test_skips_snapshots_for_deletes(self, mock_gen_msg):
        mock_gen_msg.return_value = "Delete queue"

        commit_store = MagicMock()
        commit_store.get_latest_hash.return_value = None
        snapshot_store = MagicMock()
        tracking_conn = MagicMock()
        tracking_conn.get_changes.return_value = [_make_change(operation="delete", before={"name": "Q1"}, after=None)]

        service = CommitService(commit_store, snapshot_store)
        service.create_commit(
            tracking_conn,
            chat_id="chat_1",
            user_request="Delete queue",
            environment="https://example.rossum.app",
        )

        snapshot_store.save_snapshot.assert_not_called()


class TestFormatChangesForMessage:
    def test_format_with_names(self):
        changes = [
            _make_change(operation="update", entity_type="schema", entity_id="100", entity_name="Invoice"),
            _make_change(operation="create", entity_type="hook", entity_id="200", entity_name="Validator"),
        ]
        result = _format_changes_for_message(changes)
        assert "- update schema 100 (Invoice)" in result
        assert "- create hook 200 (Validator)" in result

    def test_format_without_names(self):
        change = _make_change(entity_name="")
        result = _format_changes_for_message([change])
        assert result == "- update schema 100"


class TestGenerateCommitMessage:
    def test_llm_failure_falls_back(self):
        changes = [_make_change(operation="update", entity_type="schema", entity_name="Invoice")]

        with patch("rossum_agent.change_tracking.commit_service.create_bedrock_client", side_effect=Exception("boom")):
            result = generate_commit_message(changes, "Add a field")
        assert result == "update schema"

    def test_fallback_message_multiple_changes(self):
        changes = [
            _make_change(operation="create", entity_type="queue"),
            _make_change(operation="update", entity_type="schema"),
        ]
        assert _fallback_commit_message(changes) == "create/update queue, schema"
