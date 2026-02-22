"""Unit tests for slash command registry and handlers."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from rossum_agent.api.commands import (
    COMMANDS,
    CommandContext,
    execute_command,
    parse_command,
)
from rossum_agent.change_tracking.models import ConfigCommit, EntityChange
from rossum_agent.redis_storage import ChatData, ChatMetadata


def _make_ctx(
    chat_id: str = "chat_123",
    user_id: str | None = "user_42",
    credentials_api_url: str = "https://api.rossum.ai",
    chat_service: MagicMock | None = None,
    commit_store: MagicMock | None = None,
) -> CommandContext:
    return CommandContext(
        chat_id=chat_id,
        user_id=user_id,
        credentials_api_url=credentials_api_url,
        chat_service=chat_service or MagicMock(),
        commit_store=commit_store,
    )


class TestParseCommand:
    def test_slash_command(self):
        assert parse_command("/list-commands") == "/list-commands"

    def test_slash_command_with_trailing_whitespace(self):
        assert parse_command("  /list-commands  ") == "/list-commands"

    def test_slash_command_with_args(self):
        assert parse_command("/list-commits extra args") == "/list-commits"

    def test_non_command(self):
        assert parse_command("hello world") is None

    def test_empty_string(self):
        assert parse_command("") is None

    def test_just_whitespace(self):
        assert parse_command("   ") is None

    def test_case_insensitive(self):
        assert parse_command("/LIST-COMMANDS") == "/list-commands"

    def test_slash_only(self):
        assert parse_command("/") == "/"


class TestCommandRegistry:
    def test_list_commands_registered(self):
        assert "/list-commands" in COMMANDS

    def test_list_commits_registered(self):
        assert "/list-commits" in COMMANDS

    def test_list_skills_registered(self):
        assert "/list-skills" in COMMANDS

    def test_list_mcp_tools_registered(self):
        assert "/list-mcp-tools" in COMMANDS

    def test_list_agent_tools_registered(self):
        assert "/list-agent-tools" in COMMANDS

    def test_commands_have_descriptions(self):
        for cmd in COMMANDS.values():
            assert cmd.description
            assert cmd.name


class TestListCommandsHandler:
    @pytest.mark.asyncio
    async def test_returns_all_commands(self):
        ctx = _make_ctx()
        result = await execute_command("/list-commands", ctx)

        assert "Available commands" in result
        for cmd in COMMANDS.values():
            assert cmd.name in result
            assert cmd.description in result


class TestListCommitsHandler:
    @pytest.mark.asyncio
    async def test_no_commit_store(self):
        ctx = _make_ctx(commit_store=None)
        result = await execute_command("/list-commits", ctx)
        assert "not available" in result

    @pytest.mark.asyncio
    async def test_chat_not_found(self):
        chat_service = MagicMock()
        chat_service.get_chat_data.return_value = None
        ctx = _make_ctx(chat_service=chat_service, commit_store=MagicMock())
        result = await execute_command("/list-commits", ctx)
        assert "not found" in result

    @pytest.mark.asyncio
    async def test_no_commits(self):
        chat_service = MagicMock()
        chat_service.get_chat_data.return_value = ChatData(messages=[], metadata=ChatMetadata())
        ctx = _make_ctx(chat_service=chat_service, commit_store=MagicMock())
        result = await execute_command("/list-commits", ctx)
        assert "No configuration commits" in result

    @pytest.mark.asyncio
    async def test_with_commits(self):
        chat_service = MagicMock()
        metadata = ChatMetadata(config_commits=["abc123", "def456"])
        chat_service.get_chat_data.return_value = ChatData(messages=[], metadata=metadata)

        commit_store = MagicMock()
        commit1 = ConfigCommit(
            hash="abc123",
            chat_id="chat_123",
            timestamp=datetime(2026, 1, 15, 10, 30, tzinfo=UTC),
            message="Updated queue settings",
            user_request="Change queue",
            environment="https://api.rossum.ai",
            changes=[
                EntityChange(
                    entity_type="queue",
                    entity_id="123",
                    entity_name="My Queue",
                    operation="update",
                    before={},
                    after={},
                )
            ],
        )
        commit2 = ConfigCommit(
            hash="def456",
            chat_id="chat_123",
            timestamp=datetime(2026, 1, 15, 11, 0, tzinfo=UTC),
            message="Created new hook",
            user_request="Add hook",
            environment="https://api.rossum.ai",
            changes=[
                EntityChange(
                    entity_type="hook",
                    entity_id="456",
                    entity_name="My Hook",
                    operation="create",
                    before=None,
                    after={},
                ),
                EntityChange(
                    entity_type="hook",
                    entity_id="457",
                    entity_name="My Hook 2",
                    operation="create",
                    before=None,
                    after={},
                ),
            ],
        )
        commit_store.get_commit.side_effect = lambda env, h: {"abc123": commit1, "def456": commit2}.get(h)

        ctx = _make_ctx(chat_service=chat_service, commit_store=commit_store)
        result = await execute_command("/list-commits", ctx)

        assert "abc123" in result
        assert "Updated queue settings" in result
        assert "1 changes" in result
        assert "def456" in result
        assert "Created new hook" in result
        assert "2 changes" in result

    @pytest.mark.asyncio
    async def test_expired_commit(self):
        chat_service = MagicMock()
        metadata = ChatMetadata(config_commits=["expired1"])
        chat_service.get_chat_data.return_value = ChatData(messages=[], metadata=metadata)

        commit_store = MagicMock()
        commit_store.get_commit.return_value = None

        ctx = _make_ctx(chat_service=chat_service, commit_store=commit_store)
        result = await execute_command("/list-commits", ctx)

        assert "expired1" in result
        assert "expired or unavailable" in result


class TestListSkillsHandler:
    @pytest.mark.asyncio
    async def test_returns_skills_with_goals(self):
        ctx = _make_ctx()
        result = await execute_command("/list-skills", ctx)

        assert "Available skills" in result
        assert "schema-creation" in result
        assert "hooks" in result
        # Goal descriptions extracted from skill content
        assert "Create new schemas" in result

    @pytest.mark.asyncio
    async def test_skills_sorted_alphabetically(self):
        ctx = _make_ctx()
        result = await execute_command("/list-skills", ctx)

        lines = [line for line in result.split("\n") if line.startswith("- ")]
        slugs = [line.split("`")[1] for line in lines]
        assert slugs == sorted(slugs)


class TestListMcpToolsHandler:
    @pytest.mark.asyncio
    async def test_catalog_not_loaded(self):
        ctx = _make_ctx()
        with patch("rossum_agent.api.commands.get_cached_category_tool_names", return_value=None):
            result = await execute_command("/list-mcp-tools", ctx)
        assert "not loaded yet" in result

    @pytest.mark.asyncio
    async def test_with_catalog(self):
        ctx = _make_ctx()
        catalog = {
            "queues": {"list_queues", "get_queue"},
            "schemas": {"list_schemas"},
        }
        with patch("rossum_agent.api.commands.get_cached_category_tool_names", return_value=catalog):
            result = await execute_command("/list-mcp-tools", ctx)

        assert "3 tools in 2 categories" in result
        assert "queues" in result
        assert "list_queues" in result
        assert "schemas" in result


class TestListAgentToolsHandler:
    @pytest.mark.asyncio
    async def test_returns_tools(self):
        ctx = _make_ctx()
        result = await execute_command("/list-agent-tools", ctx)

        assert "Agent tools" in result
        # Some always-present tools
        assert "write_file" in result
        assert "load_skill" in result
        assert "load_tool_category" in result
        assert "load_tool" in result

    @pytest.mark.asyncio
    async def test_tools_sorted_alphabetically(self):
        ctx = _make_ctx()
        result = await execute_command("/list-agent-tools", ctx)

        lines = [line for line in result.split("\n") if line.startswith("- ")]
        names = [line.split("`")[1] for line in lines]
        assert names == sorted(names)


class TestExecuteUnknownCommand:
    @pytest.mark.asyncio
    async def test_unknown_command(self):
        ctx = _make_ctx()
        result = await execute_command("/nonexistent", ctx)
        assert "Unknown command" in result
        assert "/list-commands" in result
