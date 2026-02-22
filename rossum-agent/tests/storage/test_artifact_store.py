"""Tests for rossum_agent.storage.artifact_store module."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel
from rossum_agent.storage.artifact_store import DEFAULT_ARTIFACT_TTL, ArtifactStore, _handle_from_key
from rossum_agent.storage.handles import ArtifactHandle


class DummyModel(BaseModel):
    name: str
    value: int = 0


class DummyHandle(ArtifactHandle[DummyModel]):
    resource_type = "dummy"
    model_class = DummyModel


ENV = "https://example.rossum.app/api/v1"
FIXED_TS = datetime(2025, 6, 15, 10, 30, 45, 123456, tzinfo=UTC)


def _make_mock_client() -> MagicMock:
    client = MagicMock()
    client.pipeline.return_value = MagicMock()
    return client


def _make_handle(**overrides) -> DummyHandle:
    defaults = {"environment": ENV, "artifact_id": "test123", "timestamp": FIXED_TS}
    defaults.update(overrides)
    return DummyHandle(**defaults)


def _make_payload(**overrides) -> DummyModel:
    defaults = {"name": "test_artifact", "value": 42}
    defaults.update(overrides)
    return DummyModel(**defaults)


class TestSave:
    def test_save_uses_pipeline(self):
        client = _make_mock_client()
        store = ArtifactStore(client)
        handle = _make_handle()
        payload = _make_payload()

        store.save(handle, payload)

        pipe = client.pipeline.return_value
        pipe.setex.assert_called_once_with(handle.key, DEFAULT_ARTIFACT_TTL, payload.model_dump_json())
        pipe.zadd.assert_called_once_with(handle.index_key, {handle.key: handle.timestamp.timestamp()})
        pipe.expire.assert_called_once_with(handle.index_key, DEFAULT_ARTIFACT_TTL)
        pipe.execute.assert_called_once()

    def test_save_custom_ttl(self):
        client = _make_mock_client()
        custom_ttl = 7 * 24 * 3600
        store = ArtifactStore(client, ttl_seconds=custom_ttl)
        handle = _make_handle()
        payload = _make_payload()

        store.save(handle, payload)

        pipe = client.pipeline.return_value
        pipe.setex.assert_called_once_with(handle.key, custom_ttl, payload.model_dump_json())


class TestLoad:
    def test_load_roundtrip(self):
        client = _make_mock_client()
        store = ArtifactStore(client)
        handle = _make_handle()
        payload = _make_payload()

        client.get.return_value = payload.model_dump_json().encode()

        result = store.load(handle)

        assert result is not None
        assert result.name == payload.name
        assert result.value == payload.value
        client.get.assert_called_once_with(handle.key)

    def test_load_returns_none_for_missing(self):
        client = _make_mock_client()
        store = ArtifactStore(client)
        handle = _make_handle()

        client.get.return_value = None

        result = store.load(handle)
        assert result is None

    def test_load_handles_string_response(self):
        client = _make_mock_client()
        store = ArtifactStore(client)
        handle = _make_handle()
        payload = _make_payload()

        # Some Redis clients return strings instead of bytes
        client.get.return_value = payload.model_dump_json()

        result = store.load(handle)
        assert result is not None
        assert result.name == payload.name


class TestLoadLatest:
    def test_load_latest_returns_most_recent(self):
        client = _make_mock_client()
        store = ArtifactStore(client)
        handle = _make_handle()
        payload = _make_payload()

        client.zrevrange.return_value = [handle.key.encode()]
        client.get.return_value = payload.model_dump_json().encode()

        result = store.load_latest(DummyHandle, ENV)

        assert result is not None
        restored_handle, restored_payload = result
        assert restored_handle.environment == ENV
        assert restored_handle.artifact_id == "test123"
        assert restored_payload.name == payload.name

    def test_load_latest_returns_none_when_empty(self):
        client = _make_mock_client()
        store = ArtifactStore(client)

        client.zrevrange.return_value = []

        result = store.load_latest(DummyHandle, ENV)
        assert result is None

    def test_load_latest_returns_none_when_data_expired(self):
        client = _make_mock_client()
        store = ArtifactStore(client)
        handle = _make_handle()

        # Key exists in index but data has expired
        client.zrevrange.return_value = [handle.key.encode()]
        client.get.return_value = None

        result = store.load_latest(DummyHandle, ENV)
        assert result is None

    def test_load_latest_queries_correct_index(self):
        client = _make_mock_client()
        store = ArtifactStore(client)

        client.zrevrange.return_value = []

        store.load_latest(DummyHandle, ENV)

        expected_index = f"artifact_index:{ENV}:dummy"
        client.zrevrange.assert_called_once_with(expected_index, 0, 0)


class TestList:
    def test_list_returns_newest_first(self):
        client = _make_mock_client()
        store = ArtifactStore(client)

        ts_old = datetime(2025, 6, 14, 0, 0, 0, 0, tzinfo=UTC)
        ts_new = datetime(2025, 6, 15, 0, 0, 0, 0, tzinfo=UTC)
        handle_old = _make_handle(artifact_id="old", timestamp=ts_old)
        handle_new = _make_handle(artifact_id="new", timestamp=ts_new)
        payload_old = _make_payload(name="old_item")
        payload_new = _make_payload(name="new_item")

        # zrevrange returns newest first
        client.zrevrange.return_value = [handle_new.key.encode(), handle_old.key.encode()]

        def get_side_effect(key):
            if key == handle_new.key:
                return payload_new.model_dump_json().encode()
            if key == handle_old.key:
                return payload_old.model_dump_json().encode()
            return None

        client.get.side_effect = get_side_effect

        results = store.list_artifacts(DummyHandle, ENV)

        assert len(results) == 2
        assert results[0][1].name == "new_item"
        assert results[1][1].name == "old_item"

    def test_list_respects_limit(self):
        client = _make_mock_client()
        store = ArtifactStore(client)

        client.zrevrange.return_value = []

        store.list_artifacts(DummyHandle, ENV, limit=5)

        expected_index = f"artifact_index:{ENV}:dummy"
        client.zrevrange.assert_called_once_with(expected_index, 0, 4)

    def test_list_empty(self):
        client = _make_mock_client()
        store = ArtifactStore(client)

        client.zrevrange.return_value = []

        results = store.list_artifacts(DummyHandle, ENV)
        assert results == []

    def test_list_skips_expired_data(self):
        client = _make_mock_client()
        store = ArtifactStore(client)

        handle_valid = _make_handle(artifact_id="valid")
        handle_expired = _make_handle(artifact_id="expired")
        payload = _make_payload(name="valid_item")

        client.zrevrange.return_value = [handle_valid.key.encode(), handle_expired.key.encode()]

        def get_side_effect(key):
            if key == handle_valid.key:
                return payload.model_dump_json().encode()
            return None

        client.get.side_effect = get_side_effect

        results = store.list_artifacts(DummyHandle, ENV)

        assert len(results) == 1
        assert results[0][1].name == "valid_item"


class TestDelete:
    def test_delete_removes_key_and_index_entry(self):
        client = _make_mock_client()
        store = ArtifactStore(client)
        handle = _make_handle()

        pipe = client.pipeline.return_value
        pipe.execute.return_value = [1, 1]

        result = store.delete(handle)

        assert result is True
        pipe.delete.assert_called_once_with(handle.key)
        pipe.zrem.assert_called_once_with(handle.index_key, handle.key)
        pipe.execute.assert_called_once()

    def test_delete_returns_false_when_not_found(self):
        client = _make_mock_client()
        store = ArtifactStore(client)
        handle = _make_handle()

        pipe = client.pipeline.return_value
        pipe.execute.return_value = [0, 0]

        result = store.delete(handle)

        assert result is False


class TestHandleFromKey:
    def test_reconstruct_handle(self):
        original = _make_handle()
        reconstructed = _handle_from_key(DummyHandle, original.key)

        assert reconstructed.environment == original.environment
        assert reconstructed.artifact_id == original.artifact_id
        assert reconstructed.timestamp == original.timestamp

    def test_invalid_key_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid artifact key format"):
            _handle_from_key(DummyHandle, "not:a:valid:key")

    def test_roundtrip_preserves_timestamp(self):
        ts = datetime(2025, 12, 31, 23, 59, 59, 999999, tzinfo=UTC)
        handle = _make_handle(timestamp=ts)
        reconstructed = _handle_from_key(DummyHandle, handle.key)
        assert reconstructed.timestamp == ts

    def test_simple_environment(self):
        handle = DummyHandle(environment="prod", artifact_id="x", timestamp=FIXED_TS)
        reconstructed = _handle_from_key(DummyHandle, handle.key)
        assert reconstructed.environment == "prod"
        assert reconstructed.artifact_id == "x"
