"""Tests for rossum_mcp.tools.resource_tracking module."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from rossum_mcp.tools.resource_tracking import (
    TRACKED_RESOURCES_KEY,
    embed_tracked_resources,
    track_resource,
)


@dataclass
class FakeEntity:
    id: int
    name: str


@pytest.mark.unit
class TestTrackResource:
    def test_with_dict_input(self) -> None:
        tracked: list[dict] = []
        track_resource(tracked, "schema", 10, {"id": 10, "name": "S"})

        assert len(tracked) == 1
        assert tracked[0] == {"entity_type": "schema", "entity_id": "10", "data": {"id": 10, "name": "S"}}

    def test_with_dataclass_input(self) -> None:
        tracked: list[dict] = []
        track_resource(tracked, "engine", 5, FakeEntity(id=5, name="E"))

        assert len(tracked) == 1
        assert tracked[0] == {"entity_type": "engine", "entity_id": "5", "data": {"id": 5, "name": "E"}}

    def test_with_non_dict_input_is_skipped(self) -> None:
        tracked: list[dict] = []
        track_resource(tracked, "schema", 1, "not a dict")

        assert tracked == []

    def test_entity_id_coerced_to_string(self) -> None:
        tracked: list[dict] = []
        track_resource(tracked, "schema", 42, {"id": 42})

        assert tracked[0]["entity_id"] == "42"


@pytest.mark.unit
class TestEmbedTrackedResources:
    def test_embeds_into_dict_result(self) -> None:
        tracked = [{"entity_type": "schema", "entity_id": "1", "data": {"id": 1}}]
        result = embed_tracked_resources({"id": 100, "name": "Q"}, tracked)

        assert result[TRACKED_RESOURCES_KEY] == tracked
        assert result["id"] == 100

    def test_embeds_into_dataclass_result(self) -> None:
        tracked = [{"entity_type": "engine", "entity_id": "5", "data": {"id": 5}}]
        result = embed_tracked_resources(FakeEntity(id=10, name="X"), tracked)

        assert isinstance(result, dict)
        assert result[TRACKED_RESOURCES_KEY] == tracked
        assert result["id"] == 10

    def test_returns_original_when_tracked_empty(self) -> None:
        original = {"id": 1, "name": "Q"}
        result = embed_tracked_resources(original, [])

        assert result is original

    def test_returns_original_when_result_not_convertible(self) -> None:
        result = embed_tracked_resources("plain string", [{"entity_type": "x", "entity_id": "1", "data": {}}])

        assert result == "plain string"

    def test_does_not_mutate_original_dict(self) -> None:
        original = {"id": 1}
        tracked = [{"entity_type": "schema", "entity_id": "1", "data": {"id": 1}}]
        result = embed_tracked_resources(original, tracked)

        assert TRACKED_RESOURCES_KEY in result
        assert TRACKED_RESOURCES_KEY not in original
