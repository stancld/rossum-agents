"""Tests for rossum_agent.tools.subagents.knowledge_base module."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from rossum_agent.tools.subagents.base import SubAgentResult
from rossum_agent.tools.subagents.knowledge_base import (
    _SYSTEM_PROMPT,
    _TOOL_RESULT_INNER_LIMIT,
    _TOOL_RESULT_LIMIT,
    _TOOLS,
    KnowledgeBaseSubAgent,
    search_knowledge_base,
)


class TestConstants:
    """Test module constants."""

    def test_system_prompt_is_non_empty(self):
        """Test _SYSTEM_PROMPT is a non-empty string."""
        assert isinstance(_SYSTEM_PROMPT, str)
        assert len(_SYSTEM_PROMPT) > 50
        assert "kb_grep" in _SYSTEM_PROMPT
        assert "kb_get_article" in _SYSTEM_PROMPT

    def test_tools_list_contains_expected_tools(self):
        """Test _TOOLS contains kb_grep and kb_get_article."""
        tool_names = [t["name"] for t in _TOOLS]
        assert "kb_grep" in tool_names
        assert "kb_get_article" in tool_names
        assert len(tool_names) == 2

    def test_tool_result_limits(self):
        """Test truncation limits are reasonable."""
        assert _TOOL_RESULT_LIMIT > 0
        assert _TOOL_RESULT_INNER_LIMIT > 0
        assert _TOOL_RESULT_INNER_LIMIT < _TOOL_RESULT_LIMIT


class TestKnowledgeBaseSubAgent:
    """Test KnowledgeBaseSubAgent class."""

    def test_config(self):
        """Test sub-agent configuration."""
        agent = KnowledgeBaseSubAgent()

        assert agent.config.tool_name == "search_knowledge_base"
        assert agent.config.max_iterations == 5
        assert len(agent.config.tools) == 2

    def test_execute_tool_kb_grep(self):
        """Test execute_tool routes kb_grep correctly."""
        agent = KnowledgeBaseSubAgent()

        with patch("rossum_agent.tools.subagents.knowledge_base.kb_grep") as mock_grep:
            mock_grep.return_value = json.dumps({"status": "success", "matches": 1, "result": []})
            result = agent.execute_tool("kb_grep", {"pattern": "webhook", "case_insensitive": True})

            mock_grep.assert_called_once_with("webhook", True)
            parsed = json.loads(result)
            assert parsed["status"] == "success"

    def test_execute_tool_kb_get_article(self):
        """Test execute_tool routes kb_get_article correctly."""
        agent = KnowledgeBaseSubAgent()

        with patch("rossum_agent.tools.subagents.knowledge_base.kb_get_article") as mock_get:
            mock_get.return_value = json.dumps({"status": "success", "slug": "test", "content": "content"})
            result = agent.execute_tool("kb_get_article", {"slug": "test-article"})

            mock_get.assert_called_once_with("test-article")
            parsed = json.loads(result)
            assert parsed["status"] == "success"

    def test_execute_tool_unknown(self):
        """Test execute_tool handles unknown tool names."""
        agent = KnowledgeBaseSubAgent()
        result = agent.execute_tool("unknown_tool", {})
        parsed = json.loads(result)

        assert "error" in parsed
        assert "Unknown tool" in parsed["error"]

    def test_execute_tool_truncates_large_result(self):
        """Test that large results from result key are truncated."""
        agent = KnowledgeBaseSubAgent()

        large_result = json.dumps({"status": "success", "result": "x" * (_TOOL_RESULT_LIMIT + 1000)})
        with patch("rossum_agent.tools.subagents.knowledge_base.kb_grep", return_value=large_result):
            result = agent.execute_tool("kb_grep", {"pattern": "test"})

            assert len(result) < len(large_result)
            assert "truncated" in result

    def test_execute_tool_truncates_large_content(self):
        """Test that large results from content key are truncated."""
        agent = KnowledgeBaseSubAgent()

        large_result = json.dumps({"status": "success", "content": "x" * (_TOOL_RESULT_LIMIT + 1000)})
        with patch("rossum_agent.tools.subagents.knowledge_base.kb_get_article", return_value=large_result):
            result = agent.execute_tool("kb_get_article", {"slug": "test"})

            parsed = json.loads(result)
            assert len(parsed["content"]) <= _TOOL_RESULT_INNER_LIMIT + 50

    def test_execute_tool_default_case_insensitive(self):
        """Test kb_grep defaults case_insensitive to True."""
        agent = KnowledgeBaseSubAgent()

        with patch("rossum_agent.tools.subagents.knowledge_base.kb_grep") as mock_grep:
            mock_grep.return_value = json.dumps({"status": "success", "result": "No matches found"})
            agent.execute_tool("kb_grep", {"pattern": "test"})

            mock_grep.assert_called_once_with("test", True)

    def test_process_response_block_returns_none(self):
        """Test process_response_block always returns None."""
        agent = KnowledgeBaseSubAgent()
        result = agent.process_response_block(MagicMock(), iteration=1, max_iterations=5)
        assert result is None


class TestSearchKnowledgeBaseTool:
    """Test search_knowledge_base tool function."""

    def test_empty_query_returns_error(self):
        """Test that empty query returns error JSON."""
        result = search_knowledge_base("")
        parsed = json.loads(result)

        assert parsed["status"] == "error"
        assert "Query is required" in parsed["message"]

    def test_valid_query_runs_sub_agent(self):
        """Test that valid query creates and runs sub-agent."""
        mock_result = SubAgentResult(
            analysis="Document splitting allows splitting multi-page documents.",
            input_tokens=100,
            output_tokens=50,
            iterations_used=2,
            tool_calls=[{"tool": "kb_grep", "input": {"pattern": "splitting"}}],
        )

        with (
            patch("rossum_agent.tools.subagents.knowledge_base.KnowledgeBaseSubAgent") as mock_cls,
            patch("rossum_agent.tools.subagents.base.create_bedrock_client"),
        ):
            mock_instance = MagicMock()
            mock_instance.run.return_value = mock_result
            mock_cls.return_value = mock_instance

            result = search_knowledge_base("document splitting")

            parsed = json.loads(result)
            assert parsed["status"] == "success"
            assert "splitting" in parsed["answer"].lower()
            assert parsed["iterations"] == 2
            assert parsed["input_tokens"] == 100
            assert parsed["output_tokens"] == 50
            assert "searches" in parsed

    def test_user_query_appended_to_prompt(self):
        """Test that user_query is included in sub-agent prompt."""
        mock_result = SubAgentResult(
            analysis="Answer",
            input_tokens=50,
            output_tokens=25,
            iterations_used=1,
        )

        with patch("rossum_agent.tools.subagents.knowledge_base.KnowledgeBaseSubAgent") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.run.return_value = mock_result
            mock_cls.return_value = mock_instance

            search_knowledge_base("splitting", user_query="How do I configure document splitting?")

            call_args = mock_instance.run.call_args[0][0]
            assert "splitting" in call_args
            assert "How do I configure document splitting?" in call_args

    def test_user_query_same_as_query_not_duplicated(self):
        """Test that identical user_query and query doesn't duplicate text."""
        mock_result = SubAgentResult(
            analysis="Answer",
            input_tokens=50,
            output_tokens=25,
            iterations_used=1,
        )

        with patch("rossum_agent.tools.subagents.knowledge_base.KnowledgeBaseSubAgent") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.run.return_value = mock_result
            mock_cls.return_value = mock_instance

            search_knowledge_base("splitting", user_query="splitting")

            call_args = mock_instance.run.call_args[0][0]
            assert "Context" not in call_args

    def test_sub_agent_error_handled(self):
        """Test that sub-agent exceptions are caught and returned as error."""
        with patch(
            "rossum_agent.tools.subagents.knowledge_base.KnowledgeBaseSubAgent",
            side_effect=RuntimeError("Connection failed"),
        ):
            result = search_knowledge_base("test query")

            parsed = json.loads(result)
            assert parsed["status"] == "error"
            assert "Sub-agent error" in parsed["message"]

    def test_no_tool_calls_omits_searches_key(self):
        """Test that response without tool_calls omits searches key."""
        mock_result = SubAgentResult(
            analysis="Direct answer",
            input_tokens=50,
            output_tokens=25,
            iterations_used=1,
            tool_calls=None,
        )

        with patch("rossum_agent.tools.subagents.knowledge_base.KnowledgeBaseSubAgent") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.run.return_value = mock_result
            mock_cls.return_value = mock_instance

            result = search_knowledge_base("test")

            parsed = json.loads(result)
            assert parsed["status"] == "success"
            assert "searches" not in parsed
