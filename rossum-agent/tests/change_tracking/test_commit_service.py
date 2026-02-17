"""Tests for rossum_agent.change_tracking.commit_service module."""

from __future__ import annotations

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

        service = CommitService(store)
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

        service = CommitService(store)
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

        service = CommitService(store)
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

        service = CommitService(store)
        service.create_commit(
            tracking_conn,
            chat_id="chat_1",
            user_request="Add a field",
            environment="https://example.rossum.app",
        )

        tracking_conn.clear_changes.assert_called_once()


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
