"""Tests for rossum_agent.tools.subagents.elis_docs module."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from rossum_agent.tools.subagents.base import SubAgentResult
from rossum_agent.tools.subagents.elis_docs import (
    _SYSTEM_PROMPT,
    _TOOLS,
    ElisDocsSubAgent,
    search_elis_docs,
)


class TestConstants:
    """Test module constants."""

    def test_system_prompt_is_non_empty_string(self):
        """Test _SYSTEM_PROMPT is a non-empty string."""
        assert isinstance(_SYSTEM_PROMPT, str)
        assert len(_SYSTEM_PROMPT) > 50
        assert "OpenAPI" in _SYSTEM_PROMPT

    def test_tools_contains_expected_tools(self):
        """Test _TOOLS contains both jq and grep tools."""
        assert isinstance(_TOOLS, list)
        assert len(_TOOLS) == 2
        tool_names = {tool["name"] for tool in _TOOLS}
        assert "elis_openapi_jq" in tool_names
        assert "elis_openapi_grep" in tool_names


class TestElisDocsSubAgent:
    """Tests for ElisDocsSubAgent class."""

    def test_init_sets_correct_config(self):
        """Test agent initializes with correct configuration."""
        agent = ElisDocsSubAgent()

        assert agent.config.tool_name == "search_elis_docs"
        assert agent.config.max_iterations == 5
        assert "OpenAPI" in agent.config.system_prompt
        assert len(agent.config.tools) == 2

    def test_execute_tool_elis_openapi_jq(self):
        """Test execute_tool routes to elis_openapi_jq correctly."""
        agent = ElisDocsSubAgent()

        mock_result = '{"status": "success", "result": "["/v1/queues"]"}'
        with patch(
            "rossum_agent.tools.subagents.elis_docs.elis_openapi_jq",
            return_value=mock_result,
        ) as mock_jq:
            result = agent.execute_tool("elis_openapi_jq", {"jq_query": ".paths | keys"})

            mock_jq.assert_called_once_with(".paths | keys")
            assert result == mock_result

    def test_execute_tool_elis_openapi_grep(self):
        """Test execute_tool routes to elis_openapi_grep correctly."""
        agent = ElisDocsSubAgent()

        mock_result = '{"status": "success", "matches": 5, "result": "..."}'
        with patch(
            "rossum_agent.tools.subagents.elis_docs.elis_openapi_grep",
            return_value=mock_result,
        ) as mock_grep:
            result = agent.execute_tool("elis_openapi_grep", {"pattern": "queue", "case_insensitive": True})

            mock_grep.assert_called_once_with("queue", True)
            assert result == mock_result

    def test_execute_tool_grep_default_case_insensitive(self):
        """Test that grep defaults to case_insensitive=True."""
        agent = ElisDocsSubAgent()

        mock_result = '{"status": "success", "result": "..."}'
        with patch(
            "rossum_agent.tools.subagents.elis_docs.elis_openapi_grep",
            return_value=mock_result,
        ) as mock_grep:
            agent.execute_tool("elis_openapi_grep", {"pattern": "annotation"})

            mock_grep.assert_called_once_with("annotation", True)

    def test_execute_tool_unknown_tool(self):
        """Test execute_tool returns error for unknown tool."""
        agent = ElisDocsSubAgent()

        result = agent.execute_tool("unknown_tool", {"arg": "value"})

        parsed = json.loads(result)
        assert "error" in parsed
        assert "Unknown tool" in parsed["error"]

    def test_execute_tool_truncates_long_result_preserving_json(self):
        """Test that long results are truncated inside JSON envelope."""
        agent = ElisDocsSubAgent()

        long_result = json.dumps({"status": "success", "result": "x" * 20000})
        with patch(
            "rossum_agent.tools.subagents.elis_docs.elis_openapi_jq",
            return_value=long_result,
        ):
            result = agent.execute_tool("elis_openapi_jq", {"jq_query": "."})

            assert len(result) < len(long_result)
            # Should still be valid JSON
            parsed = json.loads(result)
            assert parsed["status"] == "success"
            assert "truncated" in parsed["result"]

    def test_process_response_block_returns_none(self):
        """Test process_response_block always returns None."""
        agent = ElisDocsSubAgent()

        result = agent.process_response_block(MagicMock(), 1, 5)

        assert result is None


class TestSearchElisDocsTool:
    """Tests for search_elis_docs tool function."""

    def test_empty_query_returns_error(self):
        """Test that empty query returns error JSON."""
        result = search_elis_docs("")

        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "Query is required" in parsed["message"]

    def test_valid_query_creates_agent_and_runs(self):
        """Test that valid query creates agent and calls run."""
        mock_result = SubAgentResult(
            analysis="The /v1/queues endpoint supports GET and POST.",
            input_tokens=100,
            output_tokens=50,
            iterations_used=2,
        )

        with patch.object(ElisDocsSubAgent, "run", return_value=mock_result) as mock_run:
            result = search_elis_docs("How to list queues?")

            mock_run.assert_called_once_with("How to list queues?")
            parsed = json.loads(result)
            assert parsed["status"] == "success"
            assert "queues endpoint" in parsed["answer"]
            assert parsed["iterations"] == 2
            assert parsed["input_tokens"] == 100
            assert parsed["output_tokens"] == 50

    def test_whitespace_query_returns_error(self):
        """Test that whitespace-only query returns error."""
        result = search_elis_docs("   ")

        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "Query is required" in parsed["message"]

    def test_agent_run_exception_returns_error(self):
        """Test that exceptions from agent.run() are caught and returned as error JSON."""
        with patch.object(ElisDocsSubAgent, "run", side_effect=RuntimeError("Bedrock exploded")):
            result = search_elis_docs("How to list queues?")

            parsed = json.loads(result)
            assert parsed["status"] == "error"
            assert "Bedrock exploded" in parsed["message"]
