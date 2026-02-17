"""Tests for rossum_agent.storage.handles module."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel
from rossum_agent.storage.handles import TIMESTAMP_FORMAT, ArtifactHandle


class DummyModel(BaseModel):
    name: str
    value: int = 0


class DummyHandle(ArtifactHandle[DummyModel]):
    resource_type = "dummy"
    model_class = DummyModel


ENV = "https://example.rossum.app/api/v1"
FIXED_TS = datetime(2025, 6, 15, 10, 30, 45, 123456, tzinfo=UTC)


class TestKeyDerivation:
    def test_key_format(self):
        handle = DummyHandle(environment=ENV, artifact_id="abc123", timestamp=FIXED_TS)
        ts_str = FIXED_TS.strftime(TIMESTAMP_FORMAT)
        expected = f"artifact:{ENV}:dummy:abc123:{ts_str}"
        assert handle.key == expected

    def test_key_timestamp_is_20_digits(self):
        handle = DummyHandle(environment=ENV, artifact_id="abc123", timestamp=FIXED_TS)
        # TIMESTAMP_FORMAT produces YYYYMMDDHHMMSSffffff = 20 digits
        ts_part = handle.key.rsplit(":", maxsplit=1)[-1]
        assert len(ts_part) == 20
        assert ts_part.isdigit()

    def test_index_key_format(self):
        handle = DummyHandle(environment=ENV, artifact_id="abc123", timestamp=FIXED_TS)
        assert handle.index_key == f"artifact_index:{ENV}:dummy"


class TestSerialization:
    def test_serialize_produces_json(self):
        handle = DummyHandle(environment=ENV, artifact_id="test", timestamp=FIXED_TS)
        payload = DummyModel(name="hello", value=42)
        data = handle.serialize(payload)
        assert '"name":"hello"' in data or '"name": "hello"' in data
        assert '"value":42' in data or '"value": 42' in data

    def test_deserialize_roundtrip(self):
        handle = DummyHandle(environment=ENV, artifact_id="test", timestamp=FIXED_TS)
        original = DummyModel(name="roundtrip", value=99)
        data = handle.serialize(original)
        restored = handle.deserialize(data)
        assert restored.name == original.name
        assert restored.value == original.value

    def test_deserialize_with_defaults(self):
        handle = DummyHandle(environment=ENV, artifact_id="test", timestamp=FIXED_TS)
        original = DummyModel(name="defaults_only")
        data = handle.serialize(original)
        restored = handle.deserialize(data)
        assert restored.name == "defaults_only"
        assert restored.value == 0


class TestDefaultTimestamp:
    def test_timestamp_auto_generated(self):
        before = datetime.now(UTC)
        handle = DummyHandle(environment=ENV, artifact_id="auto")
        after = datetime.now(UTC)
        assert before <= handle.timestamp <= after

    def test_explicit_timestamp_preserved(self):
        handle = DummyHandle(environment=ENV, artifact_id="explicit", timestamp=FIXED_TS)
        assert handle.timestamp == FIXED_TS


class TestEquality:
    def test_equal_handles(self):
        h1 = DummyHandle(environment=ENV, artifact_id="same", timestamp=FIXED_TS)
        h2 = DummyHandle(environment=ENV, artifact_id="same", timestamp=FIXED_TS)
        assert h1 == h2

    def test_different_artifact_id(self):
        h1 = DummyHandle(environment=ENV, artifact_id="aaa", timestamp=FIXED_TS)
        h2 = DummyHandle(environment=ENV, artifact_id="bbb", timestamp=FIXED_TS)
        assert h1 != h2

    def test_different_environment(self):
        h1 = DummyHandle(environment="env1", artifact_id="same", timestamp=FIXED_TS)
        h2 = DummyHandle(environment="env2", artifact_id="same", timestamp=FIXED_TS)
        assert h1 != h2

    def test_different_timestamp(self):
        ts2 = datetime(2025, 7, 1, 0, 0, 0, 0, tzinfo=UTC)
        h1 = DummyHandle(environment=ENV, artifact_id="same", timestamp=FIXED_TS)
        h2 = DummyHandle(environment=ENV, artifact_id="same", timestamp=ts2)
        assert h1 != h2
