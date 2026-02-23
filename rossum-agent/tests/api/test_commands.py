"""Unit tests for slash command registry and handlers."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from rossum_agent.api.commands import (
    COMMANDS,
    CommandContext,
    ParsedCommand,
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
    args: list[str] | None = None,
) -> CommandContext:
    return CommandContext(
        chat_id=chat_id,
        user_id=user_id,
        credentials_api_url=credentials_api_url,
        chat_service=chat_service or MagicMock(),
        commit_store=commit_store,
        args=args or [],
    )


class TestParseCommand:
    def test_slash_command(self):
        assert parse_command("/list-commands") == ParsedCommand(name="/list-commands", args=[])

    def test_slash_command_with_trailing_whitespace(self):
        assert parse_command("  /list-commands  ") == ParsedCommand(name="/list-commands", args=[])

    def test_slash_command_with_args(self):
        assert parse_command("/list-commits extra args") == ParsedCommand(name="/list-commits", args=["extra", "args"])

    def test_non_command(self):
        assert parse_command("hello world") is None

    def test_empty_string(self):
        assert parse_command("") is None

    def test_just_whitespace(self):
        assert parse_command("   ") is None

    def test_case_insensitive(self):
        assert parse_command("/LIST-COMMANDS") == ParsedCommand(name="/list-commands", args=[])

    def test_slash_only(self):
        assert parse_command("/") == ParsedCommand(name="/", args=[])


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

    def test_persona_registered(self):
        assert "/persona" in COMMANDS

    def test_commands_have_descriptions(self):
        for cmd in COMMANDS.values():
            assert cmd.description
            assert cmd.name

    def test_persona_has_argument_suggestions(self):
        cmd = COMMANDS["/persona"]
        assert len(cmd.argument_suggestions) == 2
        values = [v for v, _ in cmd.argument_suggestions]
        assert "default" in values
        assert "cautious" in values
        # Each suggestion has a description
        for _, desc in cmd.argument_suggestions:
            assert desc

    def test_other_commands_have_no_argument_suggestions(self):
        for name, cmd in COMMANDS.items():
            if name != "/persona":
                assert cmd.argument_suggestions == []


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
        assert 'queue "My Queue" [update]' in result
        assert "def456" in result
        assert "Created new hook" in result
        assert "2 changes" in result
        assert 'hook "My Hook" [create]' in result
        assert 'hook "My Hook 2" [create]' in result

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

    @pytest.mark.asyncio
    async def test_reverted_commit_shows_badge(self):
        chat_service = MagicMock()
        metadata = ChatMetadata(config_commits=["abc123"])
        chat_service.get_chat_data.return_value = ChatData(messages=[], metadata=metadata)

        commit = ConfigCommit(
            hash="abc123",
            chat_id="chat_123",
            timestamp=datetime(2026, 1, 15, 10, 30, tzinfo=UTC),
            message="Updated queue settings",
            user_request="Change queue",
            environment="https://api.rossum.ai",
            reverted=True,
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
        commit_store = MagicMock()
        commit_store.get_commit.return_value = commit

        ctx = _make_ctx(chat_service=chat_service, commit_store=commit_store)
        result = await execute_command("/list-commits", ctx)

        assert "[REVERTED]" in result
        assert "abc123" in result

    @pytest.mark.asyncio
    async def test_non_reverted_commit_has_no_badge(self):
        chat_service = MagicMock()
        metadata = ChatMetadata(config_commits=["abc123"])
        chat_service.get_chat_data.return_value = ChatData(messages=[], metadata=metadata)

        commit = ConfigCommit(
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
        commit_store = MagicMock()
        commit_store.get_commit.return_value = commit

        ctx = _make_ctx(chat_service=chat_service, commit_store=commit_store)
        result = await execute_command("/list-commits", ctx)

        assert "[REVERTED]" not in result


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
        slugs = [line.split("[")[1].split("]")[0] for line in lines]
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


class TestPersonaHandler:
    @pytest.mark.asyncio
    async def test_get_current_persona_default(self):
        chat_service = MagicMock()
        chat_service.get_chat_data.return_value = ChatData(messages=[], metadata=ChatMetadata())
        ctx = _make_ctx(chat_service=chat_service)
        result = await execute_command("/persona", ctx)
        assert "Current persona: **default**" in result
        assert "`default` (active)" in result
        assert "`cautious`" in result
        # Descriptions are shown
        assert "Balanced mode" in result
        assert "Plans first" in result

    @pytest.mark.asyncio
    async def test_get_current_persona_cautious(self):
        chat_service = MagicMock()
        chat_service.get_chat_data.return_value = ChatData(messages=[], metadata=ChatMetadata(persona="cautious"))
        ctx = _make_ctx(chat_service=chat_service)
        result = await execute_command("/persona", ctx)
        assert "Current persona: **cautious**" in result
        assert "`cautious` (active)" in result

    @pytest.mark.asyncio
    async def test_switch_persona(self):
        chat_service = MagicMock()
        metadata = ChatMetadata(persona="default")
        chat_service.get_chat_data.return_value = ChatData(messages=[], metadata=metadata)
        ctx = _make_ctx(chat_service=chat_service, args=["cautious"])
        result = await execute_command("/persona", ctx)
        assert "Persona switched to **cautious**" in result
        assert "Persona: cautious" in result
        chat_service.save_messages.assert_called_once()
        saved_metadata = chat_service.save_messages.call_args.kwargs["metadata"]
        assert saved_metadata.persona == "cautious"

    @pytest.mark.asyncio
    async def test_switch_persona_case_insensitive(self):
        chat_service = MagicMock()
        chat_service.get_chat_data.return_value = ChatData(messages=[], metadata=ChatMetadata())
        ctx = _make_ctx(chat_service=chat_service, args=["CAUTIOUS"])
        result = await execute_command("/persona", ctx)
        assert "Persona switched to **cautious**" in result

    @pytest.mark.asyncio
    async def test_invalid_persona(self):
        chat_service = MagicMock()
        chat_service.get_chat_data.return_value = ChatData(messages=[], metadata=ChatMetadata())
        ctx = _make_ctx(chat_service=chat_service, args=["nonexistent"])
        result = await execute_command("/persona", ctx)
        assert "Unknown persona" in result
        assert "`nonexistent`" in result
        assert "`default`" in result
        assert "`cautious`" in result

    @pytest.mark.asyncio
    async def test_chat_not_found(self):
        chat_service = MagicMock()
        chat_service.get_chat_data.return_value = None
        ctx = _make_ctx(chat_service=chat_service)
        result = await execute_command("/persona", ctx)
        assert "not found" in result


class TestSowModeHandler:
    @pytest.mark.asyncio
    async def test_enable_sow_mode(self):
        chat_service = MagicMock()
        metadata = ChatMetadata(sow_mode=False)
        chat_service.get_chat_data.return_value = ChatData(messages=[], metadata=metadata)
        ctx = _make_ctx(chat_service=chat_service, args=["on"])
        result = await execute_command("/sow-mode", ctx)
        assert "enabled" in result
        chat_service.save_messages.assert_called_once()
        saved_metadata = chat_service.save_messages.call_args.kwargs["metadata"]
        assert saved_metadata.sow_mode is True

    @pytest.mark.asyncio
    async def test_disable_sow_mode(self):
        chat_service = MagicMock()
        metadata = ChatMetadata(sow_mode=True)
        chat_service.get_chat_data.return_value = ChatData(messages=[], metadata=metadata)
        ctx = _make_ctx(chat_service=chat_service, args=["off"])
        result = await execute_command("/sow-mode", ctx)
        assert "disabled" in result
        saved_metadata = chat_service.save_messages.call_args.kwargs["metadata"]
        assert saved_metadata.sow_mode is False

    @pytest.mark.asyncio
    async def test_no_argument_shows_current_state_disabled(self):
        chat_service = MagicMock()
        chat_service.get_chat_data.return_value = ChatData(messages=[], metadata=ChatMetadata(sow_mode=False))
        ctx = _make_ctx(chat_service=chat_service)
        result = await execute_command("/sow-mode", ctx)
        assert "currently" in result
        assert "disabled" in result
        chat_service.save_messages.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_argument_shows_current_state_enabled(self):
        chat_service = MagicMock()
        chat_service.get_chat_data.return_value = ChatData(messages=[], metadata=ChatMetadata(sow_mode=True))
        ctx = _make_ctx(chat_service=chat_service)
        result = await execute_command("/sow-mode", ctx)
        assert "currently" in result
        assert "enabled" in result
        chat_service.save_messages.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_argument_shows_usage(self):
        ctx = _make_ctx(args=["maybe"])
        result = await execute_command("/sow-mode", ctx)
        assert "Usage" in result

    @pytest.mark.asyncio
    async def test_already_enabled_no_save(self):
        chat_service = MagicMock()
        metadata = ChatMetadata(sow_mode=True)
        chat_service.get_chat_data.return_value = ChatData(messages=[], metadata=metadata)
        ctx = _make_ctx(chat_service=chat_service, args=["on"])
        result = await execute_command("/sow-mode", ctx)
        assert "already" in result
        chat_service.save_messages.assert_not_called()

    @pytest.mark.asyncio
    async def test_chat_not_found(self):
        chat_service = MagicMock()
        chat_service.get_chat_data.return_value = None
        ctx = _make_ctx(chat_service=chat_service, args=["on"])
        result = await execute_command("/sow-mode", ctx)
        assert "not found" in result

    @pytest.mark.asyncio
    async def test_sow_mode_registered(self):
        from rossum_agent.api.commands import COMMANDS

        assert "/sow-mode" in COMMANDS


class TestExecuteUnknownCommand:
    @pytest.mark.asyncio
    async def test_unknown_command(self):
        ctx = _make_ctx()
        result = await execute_command("/nonexistent", ctx)
        assert "Unknown command" in result
        assert "/list-commands" in result


class TestCommandsRoute:
    def test_commands_endpoint_includes_argument_suggestions(self):
        from fastapi.testclient import TestClient
        from rossum_agent.api.main import app

        with TestClient(app) as client:
            response = client.get("/api/v1/commands")

        assert response.status_code == 200
        data = response.json()
        persona_cmd = next(c for c in data["commands"] if c["name"] == "/persona")
        suggestions = persona_cmd["argument_suggestions"]
        assert len(suggestions) == 2
        values = [s["value"] for s in suggestions]
        assert "default" in values
        assert "cautious" in values
        for s in suggestions:
            assert s["description"]

    def test_commands_without_suggestions_have_empty_list(self):
        from fastapi.testclient import TestClient
        from rossum_agent.api.main import app

        with TestClient(app) as client:
            response = client.get("/api/v1/commands")

        data = response.json()
        for cmd in data["commands"]:
            if cmd["name"] != "/persona":
                assert cmd["argument_suggestions"] == []
