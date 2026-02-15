"""Tests for rossum_agent.tools.change_history module."""

from __future__ import annotations

import asyncio
import json
import threading
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from rossum_agent.change_tracking.models import ConfigCommit, EntityChange
from rossum_agent.tools.change_history import (
    _deduplicate_changes,
    _flush_pending_changes,
    _unwrap,
    revert_commit,
    show_change_history,
    show_commit_details,
)


def _make_commit(
    hash: str = "abc123",
    parent: str | None = None,
    message: str = "Updated queue settings",
    user_request: str = "Change queue timeout",
    changes: list[EntityChange] | None = None,
) -> ConfigCommit:
    return ConfigCommit(
        hash=hash,
        parent=parent,
        chat_id="chat_1",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        message=message,
        user_request=user_request,
        environment="https://api.elis.rossum.ai/v1",
        changes=changes or [],
    )


class TestShowChangeHistory:
    """Tests for the show_change_history tool."""

    @patch("rossum_agent.tools.change_history.get_rossum_environment")
    @patch("rossum_agent.tools.change_history.get_commit_store")
    def test_no_store(self, mock_store: MagicMock, mock_env: MagicMock) -> None:
        mock_store.return_value = None
        mock_env.return_value = None
        result = json.loads(show_change_history())
        assert result["error"] == "Change tracking not available"

    @patch("rossum_agent.tools.change_history.get_rossum_environment")
    @patch("rossum_agent.tools.change_history.get_commit_store")
    def test_empty(self, mock_store: MagicMock, mock_env: MagicMock) -> None:
        mock_env.return_value = "https://api.elis.rossum.ai/v1"
        store = MagicMock()
        store.list_commits.return_value = []
        mock_store.return_value = store
        result = json.loads(show_change_history())
        assert result["message"] == "No configuration changes recorded"

    @patch("rossum_agent.tools.change_history.get_rossum_environment")
    @patch("rossum_agent.tools.change_history.get_commit_store")
    def test_with_commits(self, mock_store: MagicMock, mock_env: MagicMock) -> None:
        mock_env.return_value = "https://api.elis.rossum.ai/v1"
        store = MagicMock()
        store.list_commits.return_value = [
            _make_commit(
                changes=[EntityChange("queue", "123", "My Queue", "update", {"timeout": 60}, {"timeout": 120})]
            )
        ]
        mock_store.return_value = store
        result = json.loads(show_change_history())
        assert len(result) == 1
        assert result[0]["hash"] == "abc123"
        assert result[0]["message"] == "Updated queue settings"
        assert result[0]["changes"] == 1
        assert result[0]["user_request"] == "Change queue timeout"
        store.list_commits.assert_called_once_with("https://api.elis.rossum.ai/v1", limit=10)


class TestShowCommitDetails:
    """Tests for the show_commit_details tool."""

    @patch("rossum_agent.tools.change_history.get_rossum_environment")
    @patch("rossum_agent.tools.change_history.get_commit_store")
    def test_found(self, mock_store: MagicMock, mock_env: MagicMock) -> None:
        mock_env.return_value = "https://api.elis.rossum.ai/v1"
        store = MagicMock()
        store.get_commit.return_value = _make_commit(
            parent="parent_hash",
            changes=[EntityChange("queue", "123", "My Queue", "update", {"timeout": 60}, {"timeout": 120})],
        )
        mock_store.return_value = store
        result = json.loads(show_commit_details(commit_hash="abc123"))
        assert result["hash"] == "abc123"
        assert result["parent"] == "parent_hash"
        assert len(result["changes"]) == 1
        assert result["changes"][0]["entity_type"] == "queue"
        assert result["changes"][0]["before"] == {"timeout": 60}
        assert result["changes"][0]["after"] == {"timeout": 120}

    @patch("rossum_agent.tools.change_history.get_rossum_environment")
    @patch("rossum_agent.tools.change_history.get_commit_store")
    def test_not_found(self, mock_store: MagicMock, mock_env: MagicMock) -> None:
        mock_env.return_value = "https://api.elis.rossum.ai/v1"
        store = MagicMock()
        store.get_commit.return_value = None
        mock_store.return_value = store
        result = json.loads(show_commit_details(commit_hash="nonexistent"))
        assert "error" in result
        assert "nonexistent" in result["error"]


class TestRevertCommit:
    """Tests for the revert_commit tool."""

    @patch("rossum_agent.tools.change_history.get_rossum_environment")
    @patch("rossum_agent.tools.change_history.get_commit_store")
    def test_not_latest(self, mock_store: MagicMock, mock_env: MagicMock) -> None:
        mock_env.return_value = "https://api.elis.rossum.ai/v1"
        store = MagicMock()
        store.get_latest_hash.return_value = "latest_hash"
        mock_store.return_value = store
        result = json.loads(revert_commit(commit_hash="old_hash"))
        assert "error" in result
        assert "latest" in result["error"].lower()

    @patch("rossum_agent.tools.change_history.get_rossum_environment")
    @patch("rossum_agent.tools.change_history.get_commit_store")
    def test_plan_for_create(self, mock_store: MagicMock, mock_env: MagicMock) -> None:
        mock_env.return_value = "https://api.elis.rossum.ai/v1"
        store = MagicMock()
        store.get_latest_hash.return_value = "abc123"
        store.get_commit.return_value = _make_commit(
            changes=[EntityChange("queue", "123", "My Queue", "create", None, {"name": "My Queue"})]
        )
        mock_store.return_value = store
        result = json.loads(revert_commit(commit_hash="abc123"))
        assert result["status"] == "partial"
        assert len(result["remaining_actions"]) == 1
        assert result["remaining_actions"][0]["action"] == "delete"
        assert result["remaining_actions"][0]["tool"] == "delete_queue"
        assert result["remaining_actions"][0]["args"] == {"queue_id": "123"}

    @patch("rossum_agent.tools.change_history.get_rossum_environment")
    @patch("rossum_agent.tools.change_history.get_commit_store")
    def test_plan_for_update(self, mock_store: MagicMock, mock_env: MagicMock) -> None:
        mock_env.return_value = "https://api.elis.rossum.ai/v1"
        store = MagicMock()
        store.get_latest_hash.return_value = "abc123"
        store.get_commit.return_value = _make_commit(
            changes=[EntityChange("queue", "123", "My Queue", "update", {"timeout": 60}, {"timeout": 120})]
        )
        mock_store.return_value = store
        result = json.loads(revert_commit(commit_hash="abc123"))
        assert result["status"] == "partial"
        assert len(result["remaining_actions"]) == 1
        assert result["remaining_actions"][0]["action"] == "restore"
        assert result["remaining_actions"][0]["tool"] == "update_queue"
        assert result["remaining_actions"][0]["restore_to"] == {"timeout": 60}

    @patch("rossum_agent.tools.change_history.get_rossum_environment")
    @patch("rossum_agent.tools.change_history.get_commit_store")
    def test_plan_for_delete(self, mock_store: MagicMock, mock_env: MagicMock) -> None:
        mock_env.return_value = "https://api.elis.rossum.ai/v1"
        store = MagicMock()
        store.get_latest_hash.return_value = "abc123"
        store.get_commit.return_value = _make_commit(
            changes=[EntityChange("queue", "123", "My Queue", "delete", {"name": "My Queue"}, None)]
        )
        mock_store.return_value = store
        result = json.loads(revert_commit(commit_hash="abc123"))
        assert result["status"] == "partial"
        assert len(result["remaining_actions"]) == 1
        assert result["remaining_actions"][0]["action"] == "recreate"
        assert result["remaining_actions"][0]["tool"] == "create_queue"
        assert result["remaining_actions"][0]["original_data"] == {"name": "My Queue"}

    @patch("rossum_agent.tools.change_history.get_mcp_event_loop")
    @patch("rossum_agent.tools.change_history.get_rossum_credentials")
    @patch("rossum_agent.tools.change_history.get_rossum_environment")
    @patch("rossum_agent.tools.change_history.get_commit_store")
    @patch("rossum_agent.tools.change_history.AsyncRossumAPIClient")
    def test_direct_revert_schema_update(
        self,
        mock_client_cls: MagicMock,
        mock_store: MagicMock,
        mock_env: MagicMock,
        mock_creds: MagicMock,
        mock_loop: MagicMock,
    ) -> None:
        mock_env.return_value = "https://api.elis.rossum.ai/v1"
        mock_creds.return_value = ("https://api.elis.rossum.ai/v1", "test-token")

        loop = asyncio.new_event_loop()
        thread = threading.Thread(target=loop.run_forever)
        thread.start()
        mock_loop.return_value = loop

        mock_http_client = MagicMock()
        mock_http_client.update = AsyncMock()
        mock_client_instance = MagicMock()
        mock_client_instance._http_client = mock_http_client
        mock_client_cls.return_value = mock_client_instance

        before_schema = {"name": "Invoice", "content": [{"category": "datapoint"}]}
        after_schema = {"name": "Invoice", "content": [{"category": "datapoint"}, {"category": "new"}]}
        store = MagicMock()
        store.get_latest_hash.return_value = "abc123"
        store.get_commit.return_value = _make_commit(
            changes=[EntityChange("schema", "456", "Invoice", "update", before_schema, after_schema)]
        )
        mock_store.return_value = store

        try:
            result = json.loads(revert_commit(commit_hash="abc123"))
        finally:
            loop.call_soon_threadsafe(loop.stop)
            thread.join()
            loop.close()

        assert result["status"] == "completed"
        assert len(result["executed"]) == 1
        assert result["executed"][0]["entity_type"] == "schema"
        assert result["executed"][0]["entity_id"] == "456"
        assert "remaining_actions" not in result
        mock_http_client.update.assert_called_once()
        # Only content should be sent, not the full snapshot with read-only fields
        call_args = mock_http_client.update.call_args
        restored_data = call_args.args[2]
        assert list(restored_data.keys()) == ["content"]
        assert restored_data["content"] == [{"category": "datapoint"}]


class TestFlushPendingChanges:
    """Tests for the _flush_pending_changes helper."""

    @patch("rossum_agent.tools.change_history.get_mcp_connection")
    def test_no_connection(self, mock_conn: MagicMock) -> None:
        mock_conn.return_value = None
        store = MagicMock()
        _flush_pending_changes(store, "https://api.elis.rossum.ai/v1")
        store.save_commit.assert_not_called()

    @patch("rossum_agent.tools.change_history.get_mcp_connection")
    def test_no_pending_changes(self, mock_conn: MagicMock) -> None:
        conn = MagicMock()
        conn.has_changes.return_value = False
        mock_conn.return_value = conn
        store = MagicMock()
        _flush_pending_changes(store, "https://api.elis.rossum.ai/v1")
        store.save_commit.assert_not_called()

    @patch("rossum_agent.tools.change_history.CommitService")
    @patch("rossum_agent.tools.change_history.get_mcp_connection")
    def test_flushes_pending_changes(self, mock_conn: MagicMock, mock_service_cls: MagicMock) -> None:
        conn = MagicMock()
        conn.has_changes.return_value = True
        conn.chat_id = "test-chat"
        mock_conn.return_value = conn

        store = MagicMock()
        _flush_pending_changes(store, "https://api.elis.rossum.ai/v1")

        mock_service_cls.assert_called_once_with(store)
        mock_service_cls.return_value.create_commit.assert_called_once_with(
            conn, "test-chat", "", "https://api.elis.rossum.ai/v1"
        )

    @patch("rossum_agent.tools.change_history.CommitService")
    @patch("rossum_agent.tools.change_history.get_mcp_connection")
    def test_uses_unknown_chat_id_when_none(self, mock_conn: MagicMock, mock_service_cls: MagicMock) -> None:
        conn = MagicMock()
        conn.has_changes.return_value = True
        conn.chat_id = None
        mock_conn.return_value = conn

        store = MagicMock()
        _flush_pending_changes(store, "https://api.elis.rossum.ai/v1")

        mock_service_cls.return_value.create_commit.assert_called_once_with(
            conn, "unknown", "", "https://api.elis.rossum.ai/v1"
        )

    @patch("rossum_agent.tools.change_history._flush_pending_changes")
    @patch("rossum_agent.tools.change_history.get_rossum_environment")
    @patch("rossum_agent.tools.change_history.get_commit_store")
    def test_show_change_history_flushes_before_listing(
        self, mock_store: MagicMock, mock_env: MagicMock, mock_flush: MagicMock
    ) -> None:
        env = "https://api.elis.rossum.ai/v1"
        mock_env.return_value = env
        store = MagicMock()
        store.list_commits.return_value = []
        mock_store.return_value = store

        show_change_history()
        mock_flush.assert_called_once_with(store, env)

    @patch("rossum_agent.tools.change_history._flush_pending_changes")
    @patch("rossum_agent.tools.change_history.get_rossum_environment")
    @patch("rossum_agent.tools.change_history.get_commit_store")
    def test_revert_commit_flushes_before_reverting(
        self, mock_store: MagicMock, mock_env: MagicMock, mock_flush: MagicMock
    ) -> None:
        env = "https://api.elis.rossum.ai/v1"
        mock_env.return_value = env
        store = MagicMock()
        store.get_latest_hash.return_value = "abc123"
        store.get_commit.return_value = _make_commit(
            changes=[EntityChange("queue", "123", "My Queue", "create", None, {"name": "My Queue"})]
        )
        mock_store.return_value = store

        revert_commit(commit_hash="abc123")
        mock_flush.assert_called_once_with(store, env)


class TestUnwrap:
    def test_unwraps_result_key(self) -> None:
        assert _unwrap({"result": {"id": 1, "name": "Test"}}) == {"id": 1, "name": "Test"}

    def test_returns_as_is_when_no_result(self) -> None:
        data = {"id": 1, "name": "Test"}
        assert _unwrap(data) == data

    def test_returns_as_is_when_result_is_not_dict(self) -> None:
        data = {"result": "not a dict"}
        assert _unwrap(data) == data


class TestDeduplicateChanges:
    def test_no_duplicates(self) -> None:
        changes = [
            EntityChange("queue", "1", "Q1", "create", None, {"name": "Q1"}),
            EntityChange("schema", "2", "S1", "update", {"content": []}, {"content": [{"id": "f1"}]}),
        ]
        result = _deduplicate_changes(changes)
        assert len(result) == 2
        assert result[0] is changes[0]
        assert result[1] is changes[1]

    def test_same_entity_updated_twice(self) -> None:
        original = {"id": 100, "content": [{"id": "f1"}, {"id": "f2"}]}
        pruned = {"id": 100, "content": []}
        patched = {"id": 100, "content": [{"id": "formula1"}]}

        changes = [
            EntityChange("schema", "100", "Invoice", "update", original, pruned),
            EntityChange("schema", "100", "Invoice", "update", pruned, patched),
        ]
        result = _deduplicate_changes(changes)

        assert len(result) == 1
        assert result[0].before == original
        assert result[0].after == patched
        assert result[0].operation == "update"

    def test_three_updates_keeps_first_before_last_after(self) -> None:
        changes = [
            EntityChange("schema", "1", "S", "update", {"v": 1}, {"v": 2}),
            EntityChange("schema", "1", "S", "update", {"v": 2}, {"v": 3}),
            EntityChange("schema", "1", "S", "update", {"v": 3}, {"v": 4}),
        ]
        result = _deduplicate_changes(changes)

        assert len(result) == 1
        assert result[0].before == {"v": 1}
        assert result[0].after == {"v": 4}

    def test_mixed_entities_only_dedupes_same(self) -> None:
        changes = [
            EntityChange("queue", "1", "Q", "create", None, {"name": "Q"}),
            EntityChange("schema", "2", "S", "update", {"v": 1}, {"v": 2}),
            EntityChange("schema", "2", "S", "update", {"v": 2}, {"v": 3}),
        ]
        result = _deduplicate_changes(changes)

        assert len(result) == 2
        assert result[0].entity_type == "queue"
        assert result[1].entity_type == "schema"
        assert result[1].before == {"v": 1}
        assert result[1].after == {"v": 3}

    def test_preserves_entity_name_from_first(self) -> None:
        changes = [
            EntityChange("schema", "1", "Invoice", "update", {"v": 1}, {"v": 2}),
            EntityChange("schema", "1", "", "update", {"v": 2}, {"v": 3}),
        ]
        result = _deduplicate_changes(changes)
        assert result[0].entity_name == "Invoice"

    def test_create_then_delete_is_noop(self) -> None:
        """Create + delete of same entity → no-op, dropped from result."""
        changes = [
            EntityChange("queue", "1", "Q", "create", None, {"name": "Q"}),
            EntityChange("hook", "5", "H", "create", None, {"name": "H"}),
            EntityChange("hook", "5", "H", "delete", {"name": "H"}, None),
        ]
        result = _deduplicate_changes(changes)
        assert len(result) == 1
        assert result[0].entity_type == "queue"

    def test_create_then_delete_with_other_entities_preserved(self) -> None:
        """Only the no-op entity is dropped; other entities kept."""
        changes = [
            EntityChange("queue", "1", "Q1", "create", None, {"name": "Q1"}),
            EntityChange("hook", "5", "H", "create", None, {"name": "H"}),
            EntityChange("schema", "10", "S", "update", {"v": 1}, {"v": 2}),
            EntityChange("hook", "5", "H", "delete", {"name": "H"}, None),
        ]
        result = _deduplicate_changes(changes)
        assert len(result) == 2
        assert result[0].entity_type == "queue"
        assert result[1].entity_type == "schema"


class TestRevertWithResultWrapper:
    """Tests that revert correctly unwraps FastMCP's {"result": ...} wrapper."""

    @patch("rossum_agent.tools.change_history.get_mcp_event_loop")
    @patch("rossum_agent.tools.change_history.get_rossum_credentials")
    @patch("rossum_agent.tools.change_history.get_rossum_environment")
    @patch("rossum_agent.tools.change_history.get_commit_store")
    @patch("rossum_agent.tools.change_history.AsyncRossumAPIClient")
    def test_revert_unwraps_result_before_api_call(
        self,
        mock_client_cls: MagicMock,
        mock_store: MagicMock,
        mock_env: MagicMock,
        mock_creds: MagicMock,
        mock_loop: MagicMock,
    ) -> None:
        mock_env.return_value = "https://api.elis.rossum.ai/v1"
        mock_creds.return_value = ("https://api.elis.rossum.ai/v1", "test-token")

        loop = asyncio.new_event_loop()
        thread = threading.Thread(target=loop.run_forever)
        thread.start()
        mock_loop.return_value = loop

        mock_http_client = MagicMock()
        mock_http_client.update = AsyncMock()
        mock_client_instance = MagicMock()
        mock_client_instance._http_client = mock_http_client
        mock_client_cls.return_value = mock_client_instance

        # Snapshot wrapped in {"result": {...}} as FastMCP returns
        before_schema = {"result": {"id": 456, "name": "Invoice", "content": [{"category": "datapoint"}]}}
        after_schema = {"result": {"id": 456, "name": "Invoice", "content": []}}
        store = MagicMock()
        store.get_latest_hash.return_value = "abc123"
        store.get_commit.return_value = _make_commit(
            changes=[EntityChange("schema", "456", "Invoice", "update", before_schema, after_schema)]
        )
        mock_store.return_value = store

        try:
            result = json.loads(revert_commit(commit_hash="abc123"))
        finally:
            loop.call_soon_threadsafe(loop.stop)
            thread.join()
            loop.close()

        assert result["status"] == "completed"
        assert len(result["executed"]) == 1

        # Verify the API received only content, unwrapped from {"result": ...}
        call_args = mock_http_client.update.call_args
        restored_data = call_args.args[2]
        assert list(restored_data.keys()) == ["content"]
        assert restored_data["content"] == [{"category": "datapoint"}]

    @patch("rossum_agent.tools.change_history.get_mcp_event_loop")
    @patch("rossum_agent.tools.change_history.get_rossum_credentials")
    @patch("rossum_agent.tools.change_history.get_rossum_environment")
    @patch("rossum_agent.tools.change_history.get_commit_store")
    @patch("rossum_agent.tools.change_history.AsyncRossumAPIClient")
    def test_revert_deduplicates_multiple_schema_updates(
        self,
        mock_client_cls: MagicMock,
        mock_store: MagicMock,
        mock_env: MagicMock,
        mock_creds: MagicMock,
        mock_loop: MagicMock,
    ) -> None:
        """Prune + patch on same schema should revert to the pre-prune state."""
        mock_env.return_value = "https://api.elis.rossum.ai/v1"
        mock_creds.return_value = ("https://api.elis.rossum.ai/v1", "test-token")

        loop = asyncio.new_event_loop()
        thread = threading.Thread(target=loop.run_forever)
        thread.start()
        mock_loop.return_value = loop

        mock_http_client = MagicMock()
        mock_http_client.update = AsyncMock()
        mock_client_instance = MagicMock()
        mock_client_instance._http_client = mock_http_client
        mock_client_cls.return_value = mock_client_instance

        original = {"id": 100, "name": "Invoice", "content": [{"id": "f1"}, {"id": "f2"}]}
        pruned = {"id": 100, "name": "Invoice", "content": []}
        patched = {"id": 100, "name": "Invoice", "content": [{"id": "formula1"}]}

        store = MagicMock()
        store.get_latest_hash.return_value = "abc123"
        store.get_commit.return_value = _make_commit(
            changes=[
                EntityChange("queue", "42", "My Queue", "create", None, {"id": 42, "name": "My Queue"}),
                EntityChange("schema", "100", "Invoice", "update", original, pruned),
                EntityChange("schema", "100", "Invoice", "update", pruned, patched),
            ]
        )
        mock_store.return_value = store

        try:
            result = json.loads(revert_commit(commit_hash="abc123"))
        finally:
            loop.call_soon_threadsafe(loop.stop)
            thread.join()
            loop.close()

        assert result["status"] == "partial"
        # Only one schema revert (deduplicated), plus one queue delete plan
        assert len(result["executed"]) == 1
        assert result["executed"][0]["entity_id"] == "100"
        assert len(result["remaining_actions"]) == 1
        assert result["remaining_actions"][0]["action"] == "delete"

        # API called once with only the content from the original (pre-prune) state
        mock_http_client.update.assert_called_once()
        restored_data = mock_http_client.update.call_args.args[2]
        assert list(restored_data.keys()) == ["content"]
        assert restored_data["content"] == original["content"]
