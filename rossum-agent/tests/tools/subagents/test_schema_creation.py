"""Tests for rossum_agent.tools.subagents.schema_creation module."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from rossum_agent.tools.core import AgentContext, set_context
from rossum_agent.tools.subagents.base import SubAgentResult
from rossum_agent.tools.subagents.schema_creation import (
    _CREATE_SCHEMA_TOOL,
    _OPUS_TOOLS,
    _SCHEMA_CREATION_SYSTEM_PROMPT,
    _call_opus_for_creation,
    _execute_opus_tool,
    create_schema_with_subagent,
)


class TestConstants:
    """Test module constants."""

    def test_system_prompt_is_goal_oriented(self):
        """Test that system prompt follows Opus best practices."""
        assert "Goal:" in _SCHEMA_CREATION_SYSTEM_PROMPT

    def test_system_prompt_describes_schema_structure(self):
        """Test that system prompt documents schema structure."""
        assert "section" in _SCHEMA_CREATION_SYSTEM_PROMPT
        assert "datapoint" in _SCHEMA_CREATION_SYSTEM_PROMPT
        assert "multivalue" in _SCHEMA_CREATION_SYSTEM_PROMPT
        assert "tuple" in _SCHEMA_CREATION_SYSTEM_PROMPT

    def test_opus_tools_contains_create_schema(self):
        """Test that _OPUS_TOOLS contains create_schema tool."""
        tool_names = [t["name"] for t in _OPUS_TOOLS]
        assert "create_schema" in tool_names

    def test_create_schema_tool_schema(self):
        """Test create_schema tool has correct schema."""
        assert _CREATE_SCHEMA_TOOL["name"] == "create_schema"
        assert "name" in _CREATE_SCHEMA_TOOL["input_schema"]["required"]
        assert "content" in _CREATE_SCHEMA_TOOL["input_schema"]["required"]


class TestExecuteOpusTool:
    """Test _execute_opus_tool function."""

    def test_unknown_tool_returns_error(self):
        """Test that unknown tool returns error message."""
        result = _execute_opus_tool("unknown_tool", {})
        assert "Unknown tool" in result

    def test_create_schema_calls_mcp(self):
        """Test create_schema tool calls MCP."""
        with patch("rossum_agent.tools.subagents.schema_creation.call_mcp_tool") as mock_mcp:
            mock_mcp.return_value = {"id": 123, "name": "Test Schema"}
            result = _execute_opus_tool(
                "create_schema",
                {"name": "Test", "content": [{"id": "s1", "label": "Section", "category": "section", "children": []}]},
            )

            mock_mcp.assert_called_once()
            parsed = json.loads(result)
            assert parsed["id"] == 123

    def test_create_schema_handles_empty_response(self):
        """Test create_schema handles empty MCP response."""
        with patch("rossum_agent.tools.subagents.schema_creation.call_mcp_tool") as mock_mcp:
            mock_mcp.return_value = None
            result = _execute_opus_tool("create_schema", {"name": "Test", "content": []})

            assert result == "No data returned"


class TestCreateSchemaWithSubagent:
    """Test create_schema_with_subagent tool function."""

    def test_empty_name_returns_error(self):
        """Test that empty name returns error."""
        result = create_schema_with_subagent(name="", requirements="Create a simple schema")
        parsed = json.loads(result)

        assert "error" in parsed
        assert "name" in parsed["error"]

    def test_empty_requirements_returns_error(self):
        """Test that empty requirements returns error."""
        result = create_schema_with_subagent(name="Test Schema", requirements="")
        parsed = json.loads(result)

        assert "error" in parsed
        assert "requirements" in parsed["error"]

    def test_valid_request_calls_opus(self):
        """Test that valid request calls Opus sub-agent."""
        mock_result = SubAgentResult(
            analysis="Created schema with 2 sections",
            input_tokens=1000,
            output_tokens=500,
            iterations_used=1,
        )
        with patch(
            "rossum_agent.tools.subagents.schema_creation._call_opus_for_creation",
            return_value=mock_result,
        ) as mock_opus:
            result = create_schema_with_subagent(
                name="Invoice Schema", requirements="Create a schema with header and vendor sections"
            )
            parsed = json.loads(result)

            mock_opus.assert_called_once_with("Invoice Schema", "Create a schema with header and vendor sections")
            assert parsed["name"] == "Invoice Schema"
            assert "Created schema" in parsed["analysis"]
            assert parsed["input_tokens"] == 1000
            assert parsed["output_tokens"] == 500

    def test_timing_is_measured(self):
        """Test that elapsed_ms is properly measured."""
        mock_result = SubAgentResult(
            analysis="Done",
            input_tokens=100,
            output_tokens=50,
            iterations_used=1,
        )
        with patch(
            "rossum_agent.tools.subagents.schema_creation._call_opus_for_creation",
            return_value=mock_result,
        ):
            result = create_schema_with_subagent(name="Test", requirements="Simple schema")
            parsed = json.loads(result)

            assert "elapsed_ms" in parsed
            assert isinstance(parsed["elapsed_ms"], float)
            assert parsed["elapsed_ms"] >= 0


class TestCallOpusForCreation:
    """Test _call_opus_for_creation function."""

    def test_reports_progress(self):
        """Test that progress is reported during creation."""
        progress_calls: list = []

        mock_response = MagicMock()
        mock_response.stop_reason = "end_of_turn"
        mock_response.content = [MagicMock(text="Schema created", type="text")]
        mock_response.content[0].text = "Schema created"
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50

        set_context(
            AgentContext(
                progress_callback=lambda p: progress_calls.append(p),
                token_callback=MagicMock(),
            )
        )
        try:
            with patch("rossum_agent.tools.subagents.base.create_bedrock_client") as mock_client:
                mock_client.return_value.messages.create.return_value = mock_response

                _call_opus_for_creation("Test Schema", "Simple schema with one section")

                assert len(progress_calls) >= 1
                assert progress_calls[0].tool_name == "create_schema"
        finally:
            set_context(AgentContext())

    def test_iterates_with_tool_use(self):
        """Test that sub-agent iterates when tools are used."""
        tool_use_block = MagicMock()
        tool_use_block.type = "tool_use"
        tool_use_block.name = "create_schema"
        tool_use_block.input = {"name": "Test", "content": []}
        tool_use_block.id = "tool_1"

        first_response = MagicMock()
        first_response.stop_reason = "tool_use"
        first_response.content = [tool_use_block]
        first_response.usage.input_tokens = 100
        first_response.usage.output_tokens = 50

        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Schema created successfully"

        second_response = MagicMock()
        second_response.stop_reason = "end_of_turn"
        second_response.content = [text_block]
        second_response.usage.input_tokens = 200
        second_response.usage.output_tokens = 100

        set_context(AgentContext(progress_callback=MagicMock(), token_callback=MagicMock()))
        try:
            with (
                patch("rossum_agent.tools.subagents.base.create_bedrock_client") as mock_client,
                patch(
                    "rossum_agent.tools.subagents.schema_creation._execute_opus_tool",
                    return_value='{"id": 123, "name": "Test"}',
                ),
            ):
                mock_client.return_value.messages.create.side_effect = [first_response, second_response]

                result = _call_opus_for_creation("Test", "Simple schema")

                assert "Schema created successfully" in result.analysis
                assert result.input_tokens == 300
                assert result.output_tokens == 150
                assert mock_client.return_value.messages.create.call_count == 2
        finally:
            set_context(AgentContext())

    def test_max_iterations_is_3(self):
        """Test that max iterations is set to 3 for schema creation."""
        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "create_schema"
        mock_tool_block.input = {"name": "Test", "content": []}
        mock_tool_block.id = "tool_1"

        mock_response = MagicMock()
        mock_response.stop_reason = "tool_use"
        mock_response.content = [mock_tool_block]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50

        set_context(AgentContext(progress_callback=MagicMock(), token_callback=MagicMock()))
        try:
            with (
                patch("rossum_agent.tools.subagents.base.create_bedrock_client") as mock_client,
                patch(
                    "rossum_agent.tools.subagents.schema_creation._execute_opus_tool",
                    return_value='{"id": 123}',
                ),
                patch("rossum_agent.tools.subagents.base.logger"),
            ):
                mock_client.return_value.messages.create.return_value = mock_response

                result = _call_opus_for_creation("Test", "Simple schema")

                assert result.iterations_used == 3
                assert mock_client.return_value.messages.create.call_count == 3
        finally:
            set_context(AgentContext())

    def test_bedrock_client_exception_returns_error(self):
        """Test that create_bedrock_client exception returns error message."""
        with patch(
            "rossum_agent.tools.subagents.base.create_bedrock_client",
            side_effect=Exception("AWS error"),
        ):
            result = _call_opus_for_creation("Test", "Simple schema")

            assert "Error calling Opus sub-agent" in result.analysis
            assert "AWS error" in result.analysis
            assert result.input_tokens == 0
            assert result.output_tokens == 0
