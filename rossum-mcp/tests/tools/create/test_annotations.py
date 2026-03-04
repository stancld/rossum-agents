"""Tests for rossum_mcp.tools.create.annotations module."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest
from rossum_mcp.tools import base
from rossum_mcp.tools.create.handler import register_create_tools

if TYPE_CHECKING:
    from pathlib import Path

    from _pytest.monkeypatch import MonkeyPatch


@pytest.fixture
def mock_client() -> AsyncMock:
    """Create a mock AsyncRossumAPIClient."""
    client = AsyncMock()
    client._http_client = AsyncMock()
    client._deserializer = Mock(side_effect=lambda resource, raw: raw)
    return client


@pytest.fixture
def mock_mcp() -> Mock:
    """Create a mock FastMCP instance that captures registered tools."""
    tools: dict = {}

    def tool_decorator(**kwargs):
        def wrapper(fn):
            tools[fn.__name__] = fn
            return fn

        return wrapper

    mcp = Mock()
    mcp.tool = tool_decorator
    mcp._tools = tools
    return mcp


@pytest.mark.unit
class TestUploadDocument:
    """Tests for upload_document tool."""

    @pytest.mark.asyncio
    async def test_upload_document_success(
        self,
        mock_mcp: Mock,
        mock_client: AsyncMock,
        tmp_path: Path,
        monkeypatch: MonkeyPatch,
    ) -> None:
        """Test successful document upload."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_create_tools(mock_mcp, mock_client)

        test_file = tmp_path / "test.pdf"
        test_file.write_text("test content")

        mock_task = Mock()
        mock_task.id = 12345
        mock_task.status = "importing"
        mock_client.upload_document.return_value = [mock_task]

        upload_document = mock_mcp._tools["upload_document"]
        result = await upload_document(file_path=str(test_file), queue_id=100)

        assert result["task_id"] == 12345
        assert result["task_status"] == "importing"
        assert result["queue_id"] == 100
        assert "search" in result["message"]

    @pytest.mark.asyncio
    async def test_upload_document_file_not_found(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test upload fails when file doesn't exist."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_create_tools(mock_mcp, mock_client)

        upload_document = mock_mcp._tools["upload_document"]

        with pytest.raises(FileNotFoundError) as exc_info:
            await upload_document(file_path="/nonexistent/file.pdf", queue_id=100)

        assert "File not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_upload_document_key_error(
        self, mock_mcp: Mock, mock_client: AsyncMock, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Test upload fails when API response is missing expected key."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_create_tools(mock_mcp, mock_client)

        test_file = tmp_path / "test.pdf"
        test_file.write_text("test content")

        mock_client.upload_document.side_effect = KeyError("task")

        upload_document = mock_mcp._tools["upload_document"]

        with pytest.raises(ValueError) as exc_info:
            await upload_document(file_path=str(test_file), queue_id=100)

        assert "API response missing expected key" in str(exc_info.value)
        assert "queue_id (100)" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_upload_document_index_error(
        self, mock_mcp: Mock, mock_client: AsyncMock, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Test upload fails when API returns empty list."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_create_tools(mock_mcp, mock_client)

        test_file = tmp_path / "test.pdf"
        test_file.write_text("test content")

        mock_client.upload_document.return_value = []

        upload_document = mock_mcp._tools["upload_document"]

        with pytest.raises(ValueError) as exc_info:
            await upload_document(file_path=str(test_file), queue_id=100)

        assert "no tasks were created" in str(exc_info.value)
        assert "queue_id (100)" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_upload_document_generic_exception(
        self, mock_mcp: Mock, mock_client: AsyncMock, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Test upload fails with generic exception."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_create_tools(mock_mcp, mock_client)

        test_file = tmp_path / "test.pdf"
        test_file.write_text("test content")

        mock_client.upload_document.side_effect = RuntimeError("Connection timeout")

        upload_document = mock_mcp._tools["upload_document"]

        with pytest.raises(ValueError) as exc_info:
            await upload_document(file_path=str(test_file), queue_id=100)

        assert "Document upload failed: RuntimeError: Connection timeout" in str(exc_info.value)


@pytest.mark.unit
class TestCopyAnnotations:
    """Tests for copy_annotations (bulk) tool."""

    @pytest.mark.asyncio
    async def test_copy_annotations_success(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test successful bulk copy of annotations."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://example.rossum.app/api/v1")
        importlib.reload(base)
        register_create_tools(mock_mcp, mock_client)

        mock_client._http_client.request_json.side_effect = [
            {"id": 99991, "status": "to_review"},
            {"id": 99992, "status": "to_review"},
        ]

        copy_annotations = mock_mcp._tools["copy_annotations"]
        result = await copy_annotations(annotation_ids=[111, 222], target_queue_id=300)

        assert result["copied"] == 2
        assert result["failed"] == 0
        assert len(result["results"]) == 2
        assert result["results"][0]["annotation_id"] == 111
        assert result["results"][1]["annotation_id"] == 222

    @pytest.mark.asyncio
    async def test_copy_annotations_partial_failure(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test bulk copy where some annotations fail."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://example.rossum.app/api/v1")
        importlib.reload(base)
        register_create_tools(mock_mcp, mock_client)

        mock_client._http_client.request_json.side_effect = [
            {"id": 99991, "status": "to_review"},
            RuntimeError("Not found"),
        ]

        copy_annotations = mock_mcp._tools["copy_annotations"]
        result = await copy_annotations(annotation_ids=[111, 222], target_queue_id=300)

        assert result["copied"] == 1
        assert result["failed"] == 1
        assert result["errors"][0]["annotation_id"] == 222

    @pytest.mark.asyncio
    async def test_copy_annotations_with_reimport(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test bulk copy with reimport=True passes query param."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://example.rossum.app/api/v1")
        importlib.reload(base)
        register_create_tools(mock_mcp, mock_client)

        mock_client._http_client.request_json.return_value = {"id": 99991, "status": "importing"}

        copy_annotations = mock_mcp._tools["copy_annotations"]
        await copy_annotations(annotation_ids=[111], target_queue_id=300, reimport=True)

        call_kwargs = mock_client._http_client.request_json.call_args[1]
        assert call_kwargs["params"] == {"reimport": "true"}

    @pytest.mark.asyncio
    async def test_copy_annotations_with_target_status(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test bulk copy with target_status."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://example.rossum.app/api/v1")
        importlib.reload(base)
        register_create_tools(mock_mcp, mock_client)

        mock_client._http_client.request_json.return_value = {"id": 99991, "status": "confirmed"}

        copy_annotations = mock_mcp._tools["copy_annotations"]
        await copy_annotations(annotation_ids=[111], target_queue_id=300, target_status="confirmed")

        call_kwargs = mock_client._http_client.request_json.call_args[1]
        assert call_kwargs["json"]["target_status"] == "confirmed"
