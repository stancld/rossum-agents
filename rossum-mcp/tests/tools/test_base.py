"""Tests for rossum_mcp.tools.base module."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest


@pytest.mark.unit
class TestBuildResourceUrl:
    """Tests for build_resource_url function."""

    def test_build_resource_url_with_base_url(self) -> None:
        from rossum_mcp.tools.base import build_resource_url

        result = build_resource_url("https://api.test.rossum.ai/v1", "queues", 123)
        assert result == "https://api.test.rossum.ai/v1/queues/123"

    def test_build_resource_url_different_resources(self) -> None:
        from rossum_mcp.tools.base import build_resource_url

        base = "https://api.test.rossum.ai/v1"
        assert build_resource_url(base, "schemas", 456) == "https://api.test.rossum.ai/v1/schemas/456"
        assert build_resource_url(base, "workspaces", 789) == "https://api.test.rossum.ai/v1/workspaces/789"


@pytest.mark.unit
class TestExtractIdFromUrl:
    """Tests for extract_id_from_url function."""

    def test_extract_id_from_url(self) -> None:
        from rossum_mcp.tools.base import extract_id_from_url

        assert extract_id_from_url("https://api.test.rossum.ai/v1/queues/123") == 123

    def test_extract_id_from_url_trailing_slash(self) -> None:
        from rossum_mcp.tools.base import extract_id_from_url

        assert extract_id_from_url("https://api.test.rossum.ai/v1/queues/123/") == 123

    def test_extract_id_from_url_invalid(self) -> None:
        from rossum_mcp.tools.base import extract_id_from_url

        with pytest.raises(ValueError, match="Cannot extract resource ID"):
            extract_id_from_url("not-a-url")


@pytest.mark.unit
class TestDeleteResource:
    """Tests for delete_resource function."""

    @pytest.mark.asyncio
    async def test_delete_resource_success(self) -> None:
        from rossum_mcp.tools.base import delete_resource

        mock_delete_fn = AsyncMock()
        result = await delete_resource("queue", 123, mock_delete_fn)

        assert result == {"message": "Queue 123 deleted successfully"}
        mock_delete_fn.assert_called_once_with(123)

    @pytest.mark.asyncio
    async def test_delete_resource_custom_message(self) -> None:
        from rossum_mcp.tools.base import delete_resource

        mock_delete_fn = AsyncMock()
        result = await delete_resource("queue", 123, mock_delete_fn, "Queue 123 scheduled for deletion")

        assert result == {"message": "Queue 123 scheduled for deletion"}

    @pytest.mark.asyncio
    async def test_delete_resource_propagates_exception(self) -> None:
        from rossum_mcp.tools.base import delete_resource

        mock_delete_fn = AsyncMock(side_effect=ValueError("Not Found"))
        with pytest.raises(ValueError, match="Not Found"):
            await delete_resource("queue", 99999, mock_delete_fn)


@pytest.mark.unit
class TestGracefulList:
    """Tests for graceful_list function."""

    @pytest.mark.asyncio
    async def test_graceful_list_success(self) -> None:
        """Test graceful_list returns all items when none are broken."""
        from rossum_api.domain_logic.resources import Resource
        from rossum_mcp.tools.base import graceful_list

        client = AsyncMock()
        client._http_client = AsyncMock()
        client._deserializer = Mock(side_effect=lambda r, raw: raw)

        async def mock_fetch_all(resource, **filters):
            for item in [{"id": 1, "name": "item1"}, {"id": 2, "name": "item2"}]:
                yield item

        client._http_client.fetch_all = mock_fetch_all

        result = await graceful_list(client, Resource.Queue, "queue")
        assert len(result.items) == 2
        assert len(result.skipped_ids) == 0
        assert result.skipped_ids == []

    @pytest.mark.asyncio
    async def test_graceful_list_skips_broken_items(self) -> None:
        """Test graceful_list skips items that fail deserialization."""
        from rossum_api.domain_logic.resources import Resource
        from rossum_mcp.tools.base import graceful_list

        client = AsyncMock()
        client._http_client = AsyncMock()

        def mock_deserializer(resource, raw):
            if raw.get("id") == 2:
                raise ValueError("broken item")
            return raw

        client._deserializer = mock_deserializer

        async def mock_fetch_all(resource, **filters):
            for item in [{"id": 1, "name": "ok"}, {"id": 2, "name": "broken"}, {"id": 3, "name": "ok2"}]:
                yield item

        client._http_client.fetch_all = mock_fetch_all

        result = await graceful_list(client, Resource.Queue, "queue")
        assert len(result.items) == 2
        assert len(result.skipped_ids) == 1
        assert result.skipped_ids == [2]

    @pytest.mark.asyncio
    async def test_graceful_list_respects_max_items(self) -> None:
        """Test graceful_list respects max_items limit (counting only successful items)."""
        from rossum_api.domain_logic.resources import Resource
        from rossum_mcp.tools.base import graceful_list

        client = AsyncMock()
        client._http_client = AsyncMock()

        def mock_deserializer(resource, raw):
            if raw.get("id") == 1:
                raise ValueError("broken")
            return raw

        client._deserializer = mock_deserializer

        async def mock_fetch_all(resource, **filters):
            for item in [{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}]:
                yield item

        client._http_client.fetch_all = mock_fetch_all

        result = await graceful_list(client, Resource.Queue, "queue", max_items=2)
        assert len(result.items) == 2
        assert result.items[0]["id"] == 2
        assert result.items[1]["id"] == 3
        assert len(result.skipped_ids) == 1
        assert result.skipped_ids == [1]

    @pytest.mark.asyncio
    async def test_graceful_list_passes_filters(self) -> None:
        """Test graceful_list passes filters to fetch_all."""
        from rossum_api.domain_logic.resources import Resource
        from rossum_mcp.tools.base import graceful_list

        client = AsyncMock()
        client._http_client = AsyncMock()
        client._deserializer = Mock(side_effect=lambda r, raw: raw)

        received_filters = {}

        async def mock_fetch_all(resource, **filters):
            nonlocal received_filters
            received_filters = filters
            return
            yield

        client._http_client.fetch_all = mock_fetch_all

        await graceful_list(client, Resource.Queue, "queue", workspace=5, name="Test")
        assert received_filters == {"workspace": 5, "name": "Test"}

    @pytest.mark.asyncio
    async def test_graceful_list_all_broken(self) -> None:
        """Test graceful_list returns empty when all items fail deserialization."""
        from rossum_api.domain_logic.resources import Resource
        from rossum_mcp.tools.base import graceful_list

        client = AsyncMock()
        client._http_client = AsyncMock()
        client._deserializer = Mock(side_effect=ValueError("broken"))

        async def mock_fetch_all(resource, **filters):
            for item in [{"id": 1}, {"id": 2}]:
                yield item

        client._http_client.fetch_all = mock_fetch_all

        result = await graceful_list(client, Resource.Queue, "queue")
        assert len(result.items) == 0
        assert len(result.skipped_ids) == 2
        assert result.skipped_ids == [1, 2]

    @pytest.mark.asyncio
    async def test_graceful_list_empty(self) -> None:
        """Test graceful_list with no items."""
        from rossum_api.domain_logic.resources import Resource
        from rossum_mcp.tools.base import graceful_list

        client = AsyncMock()
        client._http_client = AsyncMock()
        client._deserializer = Mock()

        async def mock_fetch_all(resource, **filters):
            return
            yield

        client._http_client.fetch_all = mock_fetch_all

        result = await graceful_list(client, Resource.Queue, "queue")
        assert len(result.items) == 0
        assert len(result.skipped_ids) == 0
        assert result.skipped_ids == []

    @pytest.mark.asyncio
    async def test_graceful_list_logs_warning_for_broken_items(self, caplog) -> None:
        """Test graceful_list logs warnings for broken items."""
        import logging

        from rossum_api.domain_logic.resources import Resource
        from rossum_mcp.tools.base import graceful_list

        client = AsyncMock()
        client._http_client = AsyncMock()
        client._deserializer = Mock(side_effect=ValueError("bad data"))

        async def mock_fetch_all(resource, **filters):
            yield {"id": 42}

        client._http_client.fetch_all = mock_fetch_all

        with caplog.at_level(logging.WARNING):
            result = await graceful_list(client, Resource.Queue, "queue")

        assert len(result.skipped_ids) == 1
        assert "Failed to deserialize queue (id=42)" in caplog.text
        assert "Skipped 1 queue item(s)" in caplog.text
