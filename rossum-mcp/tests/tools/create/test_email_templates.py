"""Tests for rossum_mcp.tools.create.email_templates module."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest
from rossum_api.models.email_template import EmailTemplate
from rossum_mcp.tools import base
from rossum_mcp.tools.create.handler import register_create_tools

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


def create_mock_email_template(**kwargs) -> EmailTemplate:
    """Create a mock EmailTemplate dataclass instance with default values."""
    defaults = {
        "id": 1,
        "url": "https://api.test.rossum.ai/v1/email_templates/1",
        "name": "Test Email Template",
        "queue": "https://api.test.rossum.ai/v1/queues/1",
        "organization": "https://api.test.rossum.ai/v1/organizations/1",
        "subject": "Test Subject",
        "message": "<p>Test Message</p>",
        "type": "custom",
        "enabled": True,
        "automate": False,
        "triggers": [],
        "to": [],
        "cc": [],
        "bcc": [],
    }
    defaults.update(kwargs)
    return EmailTemplate(**defaults)


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
class TestCreateEmailTemplate:
    """Tests for create_email_template tool."""

    @pytest.mark.asyncio
    async def test_create_email_template_success(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test successful email template creation."""
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")

        importlib.reload(base)

        register_create_tools(mock_mcp, mock_client)

        mock_template = create_mock_email_template(
            id=200, name="New Template", subject="Welcome", message="<p>Hello</p>"
        )
        mock_client.create_new_email_template.return_value = mock_template

        create_email_template = mock_mcp._tools["create_email_template"]
        result = await create_email_template(
            name="New Template",
            queue=1,
            subject="Welcome",
            message="<p>Hello</p>",
        )

        assert result.id == 200
        assert result.name == "New Template"
        call_args = mock_client.create_new_email_template.call_args[0][0]
        assert call_args["queue"] == "https://api.test.rossum.ai/v1/queues/1"

    @pytest.mark.asyncio
    async def test_create_email_template_with_all_fields(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test email template creation with all optional fields."""
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")

        importlib.reload(base)

        register_create_tools(mock_mcp, mock_client)

        mock_template = create_mock_email_template(id=200, name="Full Template")
        mock_client.create_new_email_template.return_value = mock_template

        create_email_template = mock_mcp._tools["create_email_template"]
        result = await create_email_template(
            name="Full Template",
            queue=1,
            subject="Subject",
            message="<p>Message</p>",
            type="rejection",
            automate=True,
            to=[{"type": "constant", "value": "recipient@example.com"}],
            cc=[{"type": "annotator", "value": ""}],
            bcc=[{"type": "datapoint", "value": "email_field"}],
            triggers=["https://api.test.rossum.ai/v1/triggers/1"],
        )

        assert result.id == 200
        call_args = mock_client.create_new_email_template.call_args[0][0]
        assert call_args["name"] == "Full Template"
        assert call_args["type"] == "rejection"
        assert call_args["automate"] is True
        assert call_args["to"] == [{"type": "constant", "value": "recipient@example.com"}]
        assert call_args["cc"] == [{"type": "annotator", "value": ""}]
        assert call_args["bcc"] == [{"type": "datapoint", "value": "email_field"}]
        assert call_args["triggers"] == ["https://api.test.rossum.ai/v1/triggers/1"]
