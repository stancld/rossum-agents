"""Tests for rossum_mcp.tools.create.engines module."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest
from conftest import create_mock_engine, create_mock_engine_field
from rossum_mcp.tools import base
from rossum_mcp.tools.create.handler import register_create_tools

if TYPE_CHECKING:
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
class TestCreateEngine:
    """Tests for create_engine tool."""

    @pytest.mark.asyncio
    async def test_create_engine_success(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test successful engine creation."""
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_create_tools(mock_mcp, mock_client)

        mock_engine = create_mock_engine(id=200, name="New Engine", type="extractor")
        mock_client._http_client.create.return_value = {"id": 200}
        mock_client._deserializer = Mock(return_value=mock_engine)

        create_engine = mock_mcp._tools["create_engine"]
        result = await create_engine(name="New Engine", organization_id=1, engine_type="extractor")

        assert result.id == 200
        assert result.name == "New Engine"

    @pytest.mark.asyncio
    async def test_create_engine_invalid_type(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test create_engine with invalid engine type."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_create_tools(mock_mcp, mock_client)

        create_engine = mock_mcp._tools["create_engine"]

        with pytest.raises(ValueError) as exc_info:
            await create_engine(name="New Engine", organization_id=1, engine_type="invalid")

        assert "Invalid engine_type" in str(exc_info.value)


@pytest.mark.unit
class TestCreateEngineField:
    """Tests for create_engine_field tool."""

    @pytest.mark.asyncio
    async def test_create_engine_field_success(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test successful engine field creation."""
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_create_tools(mock_mcp, mock_client)

        mock_field = create_mock_engine_field(id=500, label="Invoice Number")
        mock_client._http_client.create.return_value = {"id": 500}
        mock_client._deserializer = Mock(return_value=mock_field)

        create_engine_field = mock_mcp._tools["create_engine_field"]
        result = await create_engine_field(
            engine_id=123,
            name="invoice_number",
            label="Invoice Number",
            field_type="string",
            schema_ids=[1, 2],
        )

        assert result.id == 500
        assert result.label == "Invoice Number"

    @pytest.mark.asyncio
    async def test_create_engine_field_empty_schemas(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test create_engine_field fails with empty schema_ids."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_create_tools(mock_mcp, mock_client)

        create_engine_field = mock_mcp._tools["create_engine_field"]

        with pytest.raises(ValueError) as exc_info:
            await create_engine_field(
                engine_id=123,
                name="field",
                label="Field",
                field_type="string",
                schema_ids=[],
            )

        assert "schema_ids cannot be empty" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_engine_field_invalid_type(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test create_engine_field fails with invalid field type."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_create_tools(mock_mcp, mock_client)

        create_engine_field = mock_mcp._tools["create_engine_field"]

        with pytest.raises(ValueError) as exc_info:
            await create_engine_field(
                engine_id=123,
                name="field",
                label="Field",
                field_type="invalid",
                schema_ids=[1],
            )

        assert "Invalid field_type" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_engine_field_with_optional_params(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test engine field creation with subtype and pre_trained_field_id."""
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_create_tools(mock_mcp, mock_client)

        mock_field = create_mock_engine_field(id=500, subtype="iban", pre_trained_field_id="iban_field")
        mock_client._http_client.create.return_value = {"id": 500}
        mock_client._deserializer = Mock(return_value=mock_field)

        create_engine_field = mock_mcp._tools["create_engine_field"]
        result = await create_engine_field(
            engine_id=123,
            name="bank_account",
            label="Bank Account",
            field_type="string",
            schema_ids=[1],
            subtype="iban",
            pre_trained_field_id="iban_field",
        )

        assert result.id == 500
        create_call = mock_client._http_client.create.call_args
        assert create_call[0][1]["subtype"] == "iban"
        assert create_call[0][1]["pre_trained_field_id"] == "iban_field"
