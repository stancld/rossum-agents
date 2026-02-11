from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from rossum_agent.api.main import app
from rossum_agent.api.routes.slack import SlackConfig, SlackContext, _fetch_slack_context, get_slack_config
from rossum_agent.api.services.slack_service import SlackServiceError

from .conftest import create_mock_httpx_client

SLACK_CONFIG = SlackConfig(bot_token="xoxb-test-token", channel="#general")


@pytest.fixture
def client(mock_chat_service, mock_agent_service, mock_file_service):
    app.state.chat_service = mock_chat_service
    app.state.agent_service = mock_agent_service
    app.state.file_service = mock_file_service
    app.dependency_overrides[get_slack_config] = lambda: SLACK_CONFIG
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
    app.dependency_overrides.pop(get_slack_config, None)


ENDPOINT = "/api/v1/chats/chat_123/report-to-slack"
SAMPLE_MESSAGES = [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi there!"}]


class TestReportToSlackEndpoint:
    @patch("rossum_agent.api.routes.slack.SlackService")
    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_report_to_slack_success(
        self, mock_httpx, mock_slack_service_cls, client, mock_chat_service, valid_headers
    ):
        mock_httpx.return_value = create_mock_httpx_client()
        mock_chat_service.chat_exists.return_value = True
        mock_chat_service.get_messages.return_value = SAMPLE_MESSAGES

        mock_slack_instance = MagicMock()
        mock_slack_instance.post_conversation = AsyncMock(return_value="1234567890.123456")
        mock_slack_service_cls.return_value = mock_slack_instance

        response = client.post(ENDPOINT, headers=valid_headers, json={})

        assert response.status_code == 200
        data = response.json()
        assert data["chat_id"] == "chat_123"
        assert data["channel"] == "#general"
        assert data["slack_ts"] == "1234567890.123456"
        mock_slack_instance.post_conversation.assert_called_once_with(
            channel="#general",
            chat_id="chat_123",
            messages=SAMPLE_MESSAGES,
            reporter_name=None,
            user_id="12345",
            organization_name=None,
            organization_id=None,
            queue_id=None,
            queue_name=None,
        )

    @patch("rossum_agent.api.routes.slack.SlackService")
    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_report_to_slack_chat_not_found(
        self, mock_httpx, mock_slack_service_cls, client, mock_chat_service, valid_headers
    ):
        mock_httpx.return_value = create_mock_httpx_client()
        mock_chat_service.chat_exists.return_value = False

        response = client.post(ENDPOINT, headers=valid_headers, json={})

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    @patch("rossum_agent.api.routes.slack.SlackService")
    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_report_to_slack_slack_error(
        self, mock_httpx, mock_slack_service_cls, client, mock_chat_service, valid_headers
    ):
        mock_httpx.return_value = create_mock_httpx_client()
        mock_chat_service.chat_exists.return_value = True
        mock_chat_service.get_messages.return_value = SAMPLE_MESSAGES

        mock_slack_instance = MagicMock()
        mock_slack_instance.post_conversation = AsyncMock(side_effect=SlackServiceError("channel_not_found"))
        mock_slack_service_cls.return_value = mock_slack_instance

        response = client.post(ENDPOINT, headers=valid_headers, json={})

        assert response.status_code == 502
        assert "channel_not_found" in response.json()["detail"]

    def test_report_to_slack_missing_auth(self, client):
        response = client.post(ENDPOINT, json={})

        assert response.status_code == 422

    @patch("rossum_agent.api.routes.slack.SlackService")
    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_report_to_slack_slack_sdk_not_installed(
        self, mock_httpx, mock_slack_service_cls, client, mock_chat_service, valid_headers
    ):
        mock_httpx.return_value = create_mock_httpx_client()
        mock_chat_service.chat_exists.return_value = True
        mock_chat_service.get_messages.return_value = SAMPLE_MESSAGES
        mock_slack_service_cls.side_effect = ImportError("Install slack extra")

        response = client.post(ENDPOINT, headers=valid_headers, json={})

        assert response.status_code == 501
        assert "Slack integration not available" in response.json()["detail"]

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_report_to_slack_missing_slack_config(
        self, mock_httpx, mock_chat_service, mock_agent_service, mock_file_service, valid_headers
    ):
        app.state.chat_service = mock_chat_service
        app.state.agent_service = mock_agent_service
        app.state.file_service = mock_file_service
        app.dependency_overrides.pop(get_slack_config, None)

        mock_httpx.return_value = create_mock_httpx_client()
        mock_chat_service.chat_exists.return_value = True
        mock_chat_service.get_messages.return_value = SAMPLE_MESSAGES

        with TestClient(app, raise_server_exceptions=False) as raw_client:
            response = raw_client.post(ENDPOINT, headers=valid_headers, json={})

        assert response.status_code == 503
        assert "SLACK_BOT_TOKEN" in response.json()["detail"]

    @patch("rossum_agent.api.routes.slack.SlackService")
    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_report_to_slack_messages_none(
        self, mock_httpx, mock_slack_service_cls, client, mock_chat_service, valid_headers
    ):
        from rossum_agent.api.routes.slack import limiter

        limiter.reset()

        mock_httpx.return_value = create_mock_httpx_client()
        mock_chat_service.chat_exists.return_value = True
        mock_chat_service.get_messages.return_value = None

        response = client.post(ENDPOINT, headers=valid_headers, json={})

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    @patch("rossum_agent.api.routes.slack.SlackService")
    @patch("rossum_agent.api.routes.slack._fetch_slack_context", new_callable=AsyncMock)
    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_report_to_slack_with_rossum_url(
        self, mock_httpx, mock_fetch_ctx, mock_slack_service_cls, client, mock_chat_service, valid_headers
    ):
        from rossum_agent.api.routes.slack import limiter

        limiter.reset()
        mock_httpx.return_value = create_mock_httpx_client()
        mock_chat_service.chat_exists.return_value = True
        mock_chat_service.get_messages.return_value = SAMPLE_MESSAGES

        mock_fetch_ctx.return_value = SlackContext(queue_name="Invoice Queue")

        mock_slack_instance = MagicMock()
        mock_slack_instance.post_conversation = AsyncMock(return_value="1234567890.123456")
        mock_slack_service_cls.return_value = mock_slack_instance

        response = client.post(
            ENDPOINT,
            headers=valid_headers,
            json={"rossum_url": "https://elis.rossum.ai/queues/3866808/settings/basic"},
        )

        assert response.status_code == 200
        mock_fetch_ctx.assert_called_once()
        call_args = mock_fetch_ctx.call_args
        assert call_args[0][1] == 3866808


class TestGetSlackConfig:
    @patch.dict("os.environ", {"SLACK_BOT_TOKEN": "xoxb-tok", "SLACK_CHANNEL": "#ch"})
    def test_returns_config_when_both_set(self):
        config = get_slack_config()
        assert config.bot_token == "xoxb-tok"
        assert config.channel == "#ch"

    @patch.dict("os.environ", {"SLACK_CHANNEL": "#ch"}, clear=True)
    def test_raises_when_token_missing(self):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            get_slack_config()
        assert exc_info.value.status_code == 503

    @patch.dict("os.environ", {"SLACK_BOT_TOKEN": "xoxb-tok"}, clear=True)
    def test_raises_when_channel_missing(self):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            get_slack_config()
        assert exc_info.value.status_code == 503


class TestFetchSlackContext:
    @pytest.fixture
    def mock_credentials(self):
        return MagicMock(api_url="https://api.rossum.ai/v1", token="test-token", user_id="123")

    @patch("rossum_agent.api.routes.slack.AsyncRossumAPIClient")
    @pytest.mark.asyncio
    async def test_success(self, mock_client_cls, mock_credentials):
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client

        mock_user = MagicMock(first_name="John", last_name="Doe", username="jdoe")
        mock_client.retrieve_user.return_value = mock_user

        mock_org = MagicMock()
        mock_org.name = "Acme Corp"
        mock_org.id = 42
        mock_client.retrieve_own_organization.return_value = mock_org

        ctx = await _fetch_slack_context(mock_credentials)

        assert ctx.reporter_name == "John Doe"
        assert ctx.user_id == "123"
        assert ctx.organization_name == "Acme Corp"
        assert ctx.organization_id == 42
        assert ctx.queue_name is None
        mock_client.retrieve_queue.assert_not_called()

    @patch("rossum_agent.api.routes.slack.AsyncRossumAPIClient")
    @pytest.mark.asyncio
    async def test_with_queue(self, mock_client_cls, mock_credentials):
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client

        mock_user = MagicMock(first_name="Jane", last_name="", username="jane")
        mock_client.retrieve_user.return_value = mock_user

        mock_org = MagicMock()
        mock_org.name = "Corp"
        mock_client.retrieve_own_organization.return_value = mock_org

        mock_queue = MagicMock()
        mock_queue.name = "Invoice Queue"
        mock_client.retrieve_queue.return_value = mock_queue

        ctx = await _fetch_slack_context(mock_credentials, queue_id=42)

        assert ctx.reporter_name == "Jane"
        assert ctx.queue_name == "Invoice Queue"
        mock_client.retrieve_queue.assert_called_once_with(42)

    @patch("rossum_agent.api.routes.slack.AsyncRossumAPIClient")
    @pytest.mark.asyncio
    async def test_api_failure_returns_empty_context(self, mock_client_cls, mock_credentials):
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client
        mock_client.retrieve_user.side_effect = Exception("API down")

        ctx = await _fetch_slack_context(mock_credentials)

        assert ctx == SlackContext(user_id="123")

    @patch("rossum_agent.api.routes.slack.AsyncRossumAPIClient")
    @pytest.mark.asyncio
    async def test_strips_trailing_slash_from_api_url(self, mock_client_cls, mock_credentials):
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client
        mock_client.retrieve_user.return_value = MagicMock(first_name="A", last_name="B", username="ab")
        mock_client.retrieve_own_organization.return_value = MagicMock(name="Org")

        mock_credentials.api_url = "https://api.rossum.ai/v1/"
        await _fetch_slack_context(mock_credentials)

        mock_client_cls.assert_called_once()
        call_kwargs = mock_client_cls.call_args
        assert call_kwargs[1]["base_url"] == "https://api.rossum.ai/v1"

    @patch("rossum_agent.api.routes.slack.AsyncRossumAPIClient")
    @pytest.mark.asyncio
    async def test_username_fallback_when_name_empty(self, mock_client_cls, mock_credentials):
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client
        mock_client.retrieve_user.return_value = MagicMock(first_name="", last_name="", username="jdoe")
        mock_client.retrieve_own_organization.return_value = MagicMock(name="Org")

        ctx = await _fetch_slack_context(mock_credentials)

        assert ctx.reporter_name == "jdoe"
