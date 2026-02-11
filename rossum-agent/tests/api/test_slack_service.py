from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rossum_agent.api.services.slack_service import SlackService, SlackServiceError


@pytest.fixture
def slack_service():
    service = SlackService(slack_bot_token="xoxb-test")
    service._client = AsyncMock()
    return service


class TestSlackServiceInit:
    def test_raises_import_error_when_slack_sdk_missing(self):
        with patch("rossum_agent.api.services.slack_service.AsyncWebClient", None):
            with pytest.raises(ImportError, match="slack-sdk is required"):
                SlackService(slack_bot_token="xoxb-test")


class TestBuildComment:
    def test_without_context(self):
        comment = SlackService._build_comment()

        assert comment == "Conversation reported"

    def test_with_reporter(self):
        comment = SlackService._build_comment(reporter_name="Jane")

        assert comment == "Conversation reported by *Jane*"

    def test_with_reporter_and_user_id(self):
        comment = SlackService._build_comment(reporter_name="Jane", user_id="456")

        assert comment == "Conversation reported by *Jane* [456]"

    def test_with_all_context(self):
        comment = SlackService._build_comment(
            reporter_name="Jane",
            user_id="456",
            organization_name="Acme",
            organization_id=789,
            queue_id=42,
            queue_name="Invoices",
        )

        assert "Conversation reported by *Jane* [456]" in comment
        assert "*Organization:* Acme [789]" in comment
        assert "*Queue:* Invoices [42]" in comment

    def test_with_partial_context(self):
        comment = SlackService._build_comment(organization_name="Acme")

        assert "Conversation reported" in comment
        assert "*Organization:* Acme" in comment
        assert "Queue" not in comment

    def test_org_id_only(self):
        comment = SlackService._build_comment(organization_id=789)

        assert "*Organization:* [789]" in comment

    def test_no_separate_user_id_or_org_id_lines(self):
        comment = SlackService._build_comment(
            reporter_name="Jane",
            user_id="456",
            organization_name="Acme",
            organization_id=789,
        )

        assert "*User ID:*" not in comment
        assert "*Organization ID:*" not in comment


class TestPostConversation:
    @pytest.mark.asyncio
    async def test_success(self, slack_service):
        slack_service._client.chat_postMessage = AsyncMock(return_value={"channel": "C123", "ts": "123.456"})
        slack_service._client.files_upload_v2 = AsyncMock()

        ts = await slack_service.post_conversation(
            channel="#test",
            chat_id="chat_1",
            messages=[{"role": "user", "content": "Hi"}],
        )

        assert ts == "123.456"
        slack_service._client.chat_postMessage.assert_called_once_with(channel="#test", text="Conversation reported")
        slack_service._client.files_upload_v2.assert_called_once()
        call_kwargs = slack_service._client.files_upload_v2.call_args[1]
        assert call_kwargs["channel"] == "C123"
        assert call_kwargs["filename"] == "chat_1.json"
        assert call_kwargs["thread_ts"] == "123.456"

    @pytest.mark.asyncio
    async def test_slack_api_error(self, slack_service):
        from slack_sdk.errors import SlackApiError

        error_response = MagicMock()
        error_response.__getitem__ = lambda self, key: "channel_not_found" if key == "error" else None
        slack_service._client.chat_postMessage = AsyncMock(
            side_effect=SlackApiError(message="error", response=error_response)
        )

        with pytest.raises(SlackServiceError, match="channel_not_found"):
            await slack_service.post_conversation(channel="#bad", chat_id="chat_1", messages=[])

    @pytest.mark.asyncio
    async def test_passes_context_to_comment(self, slack_service):
        slack_service._client.chat_postMessage = AsyncMock(return_value={"channel": "C1", "ts": "1"})
        slack_service._client.files_upload_v2 = AsyncMock()

        await slack_service.post_conversation(
            channel="#test",
            chat_id="chat_1",
            messages=[],
            reporter_name="Jane",
            organization_name="Acme",
            queue_name="Invoices",
        )

        call_kwargs = slack_service._client.chat_postMessage.call_args[1]
        assert "Jane" in call_kwargs["text"]
        assert "Acme" in call_kwargs["text"]
        assert "Invoices" in call_kwargs["text"]

    @pytest.mark.asyncio
    async def test_file_upload_error(self, slack_service):
        from slack_sdk.errors import SlackApiError

        slack_service._client.chat_postMessage = AsyncMock(return_value={"channel": "C1", "ts": "1"})
        error_response = MagicMock()
        error_response.__getitem__ = lambda self, key: "file_too_large" if key == "error" else None
        slack_service._client.files_upload_v2 = AsyncMock(
            side_effect=SlackApiError(message="error", response=error_response)
        )

        with pytest.raises(SlackServiceError, match="file_too_large"):
            await slack_service.post_conversation(channel="#test", chat_id="chat_1", messages=[])
