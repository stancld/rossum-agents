"""Tests for rossum_mcp.tools.users module."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from rossum_api.models.group import Group
from rossum_api.models.user import User
from rossum_mcp.tools.users import register_user_tools


def create_mock_user(**kwargs) -> User:
    """Create a mock User dataclass instance with default values."""
    defaults = {
        "id": 1,
        "url": "https://api.test.rossum.ai/v1/users/1",
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "date_joined": "2024-01-01T00:00:00Z",
        "username": "john.doe@example.com",
        "organization": "https://api.test.rossum.ai/v1/organizations/1",
        "last_login": "2024-01-15T10:30:00Z",
        "is_active": True,
        "email_verified": True,
        "password": None,
        "groups": [],
        "queues": [],
        "ui_settings": {},
        "metadata": {},
        "oidc_id": None,
        "auth_type": "password",
        "deleted": False,
    }
    defaults.update(kwargs)
    return User(**defaults)


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
class TestGetUser:
    """Tests for get_user tool."""

    @pytest.mark.asyncio
    async def test_get_user_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful user retrieval."""
        register_user_tools(mock_mcp, mock_client)

        mock_user = create_mock_user(id=100, username="test.user@example.com")
        mock_client.retrieve_user.return_value = mock_user

        get_user = mock_mcp._tools["get_user"]
        result = await get_user(user_id=100)

        assert result.id == 100
        assert result.username == "test.user@example.com"
        mock_client.retrieve_user.assert_called_once_with(100)


@pytest.mark.unit
class TestListUsers:
    """Tests for list_users tool."""

    @pytest.mark.asyncio
    async def test_list_users_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful users listing."""
        register_user_tools(mock_mcp, mock_client)

        mock_user1 = create_mock_user(id=1, username="user1@example.com")
        mock_user2 = create_mock_user(id=2, username="user2@example.com")

        async def mock_fetch_all(resource, **filters):
            for item in [mock_user1, mock_user2]:
                yield item

        mock_client._http_client.fetch_all = mock_fetch_all

        list_users = mock_mcp._tools["list_users"]
        result = await list_users()

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_users_with_username_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test users listing filtered by username."""
        register_user_tools(mock_mcp, mock_client)

        mock_user = create_mock_user(id=1, username="specific.user@example.com")
        received_filters: dict = {}

        async def mock_fetch_all(resource, **filters):
            nonlocal received_filters
            received_filters = filters
            yield mock_user

        mock_client._http_client.fetch_all = mock_fetch_all

        list_users = mock_mcp._tools["list_users"]
        result = await list_users(username="specific.user@example.com")

        assert len(result) == 1
        assert received_filters["username"] == "specific.user@example.com"

    @pytest.mark.asyncio
    async def test_list_users_with_email_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test users listing filtered by email."""
        register_user_tools(mock_mcp, mock_client)

        mock_user = create_mock_user(id=1, email="test@example.com")
        received_filters: dict = {}

        async def mock_fetch_all(resource, **filters):
            nonlocal received_filters
            received_filters = filters
            yield mock_user

        mock_client._http_client.fetch_all = mock_fetch_all

        list_users = mock_mcp._tools["list_users"]
        result = await list_users(email="test@example.com")

        assert len(result) == 1
        assert received_filters["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_list_users_with_is_active_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test users listing filtered by active status."""
        register_user_tools(mock_mcp, mock_client)

        mock_user = create_mock_user(id=1, is_active=True)
        received_filters: dict = {}

        async def mock_fetch_all(resource, **filters):
            nonlocal received_filters
            received_filters = filters
            yield mock_user

        mock_client._http_client.fetch_all = mock_fetch_all

        list_users = mock_mcp._tools["list_users"]
        result = await list_users(is_active=True)

        assert len(result) == 1
        assert received_filters["is_active"] is True

    @pytest.mark.asyncio
    async def test_list_users_empty_result(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test users listing when no users match."""
        register_user_tools(mock_mcp, mock_client)

        async def mock_fetch_all(resource, **filters):
            return
            yield

        mock_client._http_client.fetch_all = mock_fetch_all

        list_users = mock_mcp._tools["list_users"]
        result = await list_users()

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_list_users_with_multiple_filters(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test users listing with multiple filters."""
        register_user_tools(mock_mcp, mock_client)

        mock_user = create_mock_user(id=1, first_name="John", last_name="Doe")
        received_filters: dict = {}

        async def mock_fetch_all(resource, **filters):
            nonlocal received_filters
            received_filters = filters
            yield mock_user

        mock_client._http_client.fetch_all = mock_fetch_all

        list_users = mock_mcp._tools["list_users"]
        result = await list_users(first_name="John", last_name="Doe")

        assert len(result) == 1
        assert received_filters["first_name"] == "John"
        assert received_filters["last_name"] == "Doe"

    @pytest.mark.asyncio
    async def test_list_users_filter_is_organization_group_admin_true(
        self, mock_mcp: Mock, mock_client: AsyncMock
    ) -> None:
        """Test users listing filtered to only organization_group_admin users."""
        from rossum_api.domain_logic.resources import Resource

        register_user_tools(mock_mcp, mock_client)

        org_admin_group_url = "https://api.test.rossum.ai/v1/groups/99"
        admin_user = create_mock_user(id=1, username="admin@example.com", groups=[org_admin_group_url])
        regular_user = create_mock_user(id=2, username="regular@example.com", groups=[])
        org_admin_group = Group(id=99, url=org_admin_group_url, name="organization_group_admin")

        async def mock_fetch_all(resource, **filters):
            if resource == Resource.User:
                for user in [admin_user, regular_user]:
                    yield user
            elif resource == Resource.Group:
                yield org_admin_group

        mock_client._http_client.fetch_all = mock_fetch_all

        list_users = mock_mcp._tools["list_users"]
        result = await list_users(is_organization_group_admin=True)

        assert len(result) == 1
        assert result[0].id == 1
        assert result[0].username == "admin@example.com"

    @pytest.mark.asyncio
    async def test_list_users_filter_is_organization_group_admin_false(
        self, mock_mcp: Mock, mock_client: AsyncMock
    ) -> None:
        """Test users listing filtered to exclude organization_group_admin users."""
        from rossum_api.domain_logic.resources import Resource

        register_user_tools(mock_mcp, mock_client)

        org_admin_group_url = "https://api.test.rossum.ai/v1/groups/99"
        admin_user = create_mock_user(id=1, username="admin@example.com", groups=[org_admin_group_url])
        regular_user = create_mock_user(id=2, username="regular@example.com", groups=[])
        org_admin_group = Group(id=99, url=org_admin_group_url, name="organization_group_admin")

        async def mock_fetch_all(resource, **filters):
            if resource == Resource.User:
                for user in [admin_user, regular_user]:
                    yield user
            elif resource == Resource.Group:
                yield org_admin_group

        mock_client._http_client.fetch_all = mock_fetch_all

        list_users = mock_mcp._tools["list_users"]
        result = await list_users(is_organization_group_admin=False)

        assert len(result) == 1
        assert result[0].id == 2
        assert result[0].username == "regular@example.com"

    @pytest.mark.asyncio
    async def test_list_users_filter_is_organization_group_admin_no_admins(
        self, mock_mcp: Mock, mock_client: AsyncMock
    ) -> None:
        """Test users listing when no organization_group_admin role exists."""
        from rossum_api.domain_logic.resources import Resource

        register_user_tools(mock_mcp, mock_client)

        mock_user = create_mock_user(
            id=1, username="user@example.com", groups=["https://api.test.rossum.ai/v1/groups/1"]
        )
        annotator_group = Group(id=1, url="https://api.test.rossum.ai/v1/groups/1", name="annotator")

        async def mock_fetch_all(resource, **filters):
            if resource == Resource.User:
                yield mock_user
            elif resource == Resource.Group:
                yield annotator_group

        mock_client._http_client.fetch_all = mock_fetch_all

        list_users = mock_mcp._tools["list_users"]
        result = await list_users(is_organization_group_admin=True)

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_list_users_skips_broken_items(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test list_users gracefully skips items that fail deserialization."""
        register_user_tools(mock_mcp, mock_client)

        mock_user = create_mock_user(id=1, username="good@example.com")

        def mock_deserializer(resource, raw):
            if raw.get("id") == 2:
                raise ValueError("broken user")
            return mock_user

        mock_client._deserializer = mock_deserializer

        async def mock_fetch_all(resource, **filters):
            yield {"id": 1, "username": "good@example.com"}
            yield {"id": 2, "username": "broken@example.com"}
            yield {"id": 3, "username": "also_good@example.com"}

        mock_client._http_client.fetch_all = mock_fetch_all

        list_users = mock_mcp._tools["list_users"]
        result = await list_users()

        assert len(result) == 2


@pytest.mark.unit
class TestListUserRoles:
    """Tests for list_user_roles tool."""

    @pytest.mark.asyncio
    async def test_list_user_roles_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful user roles listing."""
        register_user_tools(mock_mcp, mock_client)

        mock_group1 = Group(id=1, url="https://api.test.rossum.ai/v1/groups/1", name="admin")
        mock_group2 = Group(id=2, url="https://api.test.rossum.ai/v1/groups/2", name="annotator")

        async def mock_fetch_all(resource, **filters):
            for item in [mock_group1, mock_group2]:
                yield item

        mock_client._http_client.fetch_all = mock_fetch_all

        list_user_roles = mock_mcp._tools["list_user_roles"]
        result = await list_user_roles()

        assert len(result) == 2
