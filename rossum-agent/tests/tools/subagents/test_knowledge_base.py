"""Tests for rossum_agent.tools.subagents.knowledge_base module."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from rossum_agent.tools.subagents.base import SubAgentResult
from rossum_agent.tools.subagents.knowledge_base import (
    _KB_PYTHON_EXEC_TOOL,
    _MAX_CODE_LENGTH,
    _SYSTEM_PROMPT,
    _TOOL_RESULT_INNER_LIMIT,
    _TOOL_RESULT_LIMIT,
    _TOOLS,
    KnowledgeBaseSubAgent,
    kb_python_exec,
    search_knowledge_base,
)


class TestConstants:
    """Test module constants."""

    def test_system_prompt_is_non_empty(self):
        assert isinstance(_SYSTEM_PROMPT, str)
        assert len(_SYSTEM_PROMPT) > 50

    def test_tools_list_contains_expected_tools(self):
        tool_names = [t["name"] for t in _TOOLS]
        assert "kb_grep" in tool_names
        assert "kb_get_article" in tool_names
        assert "kb_python_exec" in tool_names
        assert len(tool_names) == 3

    def test_tool_result_limits(self):
        assert _TOOL_RESULT_LIMIT > 0
        assert _TOOL_RESULT_INNER_LIMIT > 0
        assert _TOOL_RESULT_INNER_LIMIT < _TOOL_RESULT_LIMIT

    def test_kb_python_exec_tool_definition(self):
        assert _KB_PYTHON_EXEC_TOOL["name"] == "kb_python_exec"
        assert "articles" in _KB_PYTHON_EXEC_TOOL["description"]
        assert "spillover" in _KB_PYTHON_EXEC_TOOL["description"]
        schema = _KB_PYTHON_EXEC_TOOL["input_schema"]
        assert "code" in schema["properties"]
        assert schema["required"] == ["code"]


class TestKnowledgeBaseSubAgent:
    """Test KnowledgeBaseSubAgent class."""

    def test_config(self):
        agent = KnowledgeBaseSubAgent()

        assert agent.config.tool_name == "search_knowledge_base"
        assert agent.config.max_iterations == 4
        assert len(agent.config.tools) == 3

    def test_execute_tool_kb_grep(self):
        agent = KnowledgeBaseSubAgent()

        with patch("rossum_agent.tools.subagents.knowledge_base.kb_grep") as mock_grep:
            mock_grep.return_value = json.dumps({"status": "success", "matches": 1, "result": []})
            result = agent.execute_tool("kb_grep", {"pattern": "webhook", "case_insensitive": True})

            mock_grep.assert_called_once_with("webhook", True)
            parsed = json.loads(result)
            assert parsed["status"] == "success"

    def test_execute_tool_kb_get_article(self):
        agent = KnowledgeBaseSubAgent()

        with patch("rossum_agent.tools.subagents.knowledge_base.kb_get_article") as mock_get:
            mock_get.return_value = json.dumps({"status": "success", "slug": "test", "content": "content"})
            result = agent.execute_tool("kb_get_article", {"slug": "test-article"})

            mock_get.assert_called_once_with("test-article")
            parsed = json.loads(result)
            assert parsed["status"] == "success"

    def test_execute_tool_kb_python_exec(self):
        agent = KnowledgeBaseSubAgent()

        with patch("rossum_agent.tools.subagents.knowledge_base.kb_python_exec") as mock_exec:
            mock_exec.return_value = json.dumps({"status": "success", "result": 42})
            result = agent.execute_tool("kb_python_exec", {"code": "1 + 1"})

            mock_exec.assert_called_once_with("1 + 1")
            parsed = json.loads(result)
            assert parsed["status"] == "success"

    def test_execute_tool_unknown(self):
        agent = KnowledgeBaseSubAgent()
        result = agent.execute_tool("unknown_tool", {})
        parsed = json.loads(result)

        assert "error" in parsed
        assert "Unknown tool" in parsed["error"]

    def test_execute_tool_truncates_large_result(self):
        agent = KnowledgeBaseSubAgent()

        large_result = json.dumps({"status": "success", "result": "x" * (_TOOL_RESULT_LIMIT + 1000)})
        with patch("rossum_agent.tools.subagents.knowledge_base.kb_grep", return_value=large_result):
            result = agent.execute_tool("kb_grep", {"pattern": "test"})

            assert len(result) < len(large_result)
            assert "truncated" in result

    def test_execute_tool_truncates_large_content(self):
        agent = KnowledgeBaseSubAgent()

        large_result = json.dumps({"status": "success", "content": "x" * (_TOOL_RESULT_LIMIT + 1000)})
        with patch("rossum_agent.tools.subagents.knowledge_base.kb_get_article", return_value=large_result):
            result = agent.execute_tool("kb_get_article", {"slug": "test"})

            parsed = json.loads(result)
            assert len(parsed["content"]) <= _TOOL_RESULT_INNER_LIMIT + 50

    def test_execute_tool_default_case_insensitive(self):
        agent = KnowledgeBaseSubAgent()

        with patch("rossum_agent.tools.subagents.knowledge_base.kb_grep") as mock_grep:
            mock_grep.return_value = json.dumps({"status": "success", "result": "No matches found"})
            agent.execute_tool("kb_grep", {"pattern": "test"})

            mock_grep.assert_called_once_with("test", True)

    def test_process_response_block_returns_none(self):
        agent = KnowledgeBaseSubAgent()
        result = agent.process_response_block(MagicMock(), iteration=1, max_iterations=5)
        assert result is None


class TestKbPythonExec:
    """Test kb_python_exec function."""

    def test_simple_expression(self):
        result = kb_python_exec("1 + 2")
        parsed = json.loads(result)
        assert parsed["status"] == "success"
        assert parsed["result"] == 3

    def test_result_variable(self):
        result = kb_python_exec("result = [1, 2, 3]")
        parsed = json.loads(result)
        assert parsed["status"] == "success"
        assert parsed["result"] == [1, 2, 3]

    def test_print_captured(self):
        result = kb_python_exec('print("hello")')
        parsed = json.loads(result)
        assert parsed["status"] == "success"
        assert parsed["stdout"] == "hello\n"

    def test_articles_available(self):
        sample_data = {
            "articles": [{"slug": "test-article", "title": "Test", "url": "http://test", "content": "content"}]
        }
        with patch("rossum_agent.tools.subagents.knowledge_base._cache") as mock_cache:
            mock_cache.load.return_value = sample_data
            result = kb_python_exec("len(articles)")
            parsed = json.loads(result)
            assert parsed["status"] == "success"
            assert parsed["result"] == 1

    def test_spillover_available(self):
        import rossum_agent.tools.subagents.knowledge_base as kb_mod

        old_spillover = kb_mod._spillover
        try:
            kb_mod._spillover = [{"slug": "a", "title": "A", "url": "http://a", "snippet": "test"}]
            result = kb_python_exec("len(spillover)")
            parsed = json.loads(result)
            assert parsed["status"] == "success"
            assert parsed["result"] == 1
        finally:
            kb_mod._spillover = old_spillover

    def test_re_module_available(self):
        result = kb_python_exec("bool(re.search('test', 'this is a test'))")
        parsed = json.loads(result)
        assert parsed["status"] == "success"
        assert parsed["result"] is True

    def test_json_module_available(self):
        result = kb_python_exec('json.dumps({"a": 1})')
        parsed = json.loads(result)
        assert parsed["status"] == "success"
        assert parsed["result"] == '{"a": 1}'

    def test_collections_available(self):
        result = kb_python_exec("collections.Counter([1, 1, 2, 3])")
        parsed = json.loads(result)
        assert parsed["status"] == "success"

    def test_disallowed_class_definition(self):
        result = kb_python_exec("class Foo: pass")
        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "ClassDef" in parsed["error"]

    def test_disallowed_dunder_access(self):
        result = kb_python_exec("x = __builtins__")
        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "__" in parsed["error"]

    def test_disallowed_import(self):
        result = kb_python_exec("import os")
        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "Import not allowed" in parsed["error"]

    def test_code_length_limit(self):
        result = kb_python_exec("x = 1\n" * (_MAX_CODE_LENGTH + 1))
        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "exceeds" in parsed["error"]

    def test_runtime_error_caught(self):
        result = kb_python_exec("1 / 0")
        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "ZeroDivisionError" in parsed["error"]

    def test_output_truncation(self):
        result = kb_python_exec("'x' * 100000")
        # Should not crash, and output should be bounded
        assert len(result) <= 35000

    def test_filter_spillover_pattern(self):
        """Test the typical use case: filtering spillover from a grep."""
        import rossum_agent.tools.subagents.knowledge_base as kb_mod

        old_spillover = kb_mod._spillover
        try:
            kb_mod._spillover = [
                {
                    "slug": "webhook-config",
                    "title": "Webhook Config",
                    "url": "http://a",
                    "snippet": "configure webhooks",
                },
                {"slug": "email-import", "title": "Email Import", "url": "http://b", "snippet": "import via email"},
                {
                    "slug": "webhook-events",
                    "title": "Webhook Events",
                    "url": "http://c",
                    "snippet": "event types for webhooks",
                },
            ]
            result = kb_python_exec("[m['slug'] for m in spillover if 'webhook' in m['snippet']]")
            parsed = json.loads(result)
            assert parsed["status"] == "success"
            assert parsed["result"] == ["webhook-config", "webhook-events"]
        finally:
            kb_mod._spillover = old_spillover

    def test_allowed_import_in_code(self):
        result = kb_python_exec("import math\nmath.sqrt(4)")
        parsed = json.loads(result)
        assert parsed["status"] == "success"
        assert parsed["result"] == 2.0


class TestSearchKnowledgeBaseTool:
    """Test search_knowledge_base tool function."""

    def test_empty_query_returns_error(self):
        result = search_knowledge_base("")
        parsed = json.loads(result)

        assert parsed["status"] == "error"
        assert "Query is required" in parsed["message"]

    def test_valid_query_runs_sub_agent(self):
        mock_result = SubAgentResult(
            analysis="Document splitting allows splitting multi-page documents.",
            input_tokens=100,
            output_tokens=50,
            iterations_used=2,
            tool_calls=[{"tool": "kb_grep", "input": {"pattern": "splitting"}}],
        )

        with (
            patch("rossum_agent.tools.subagents.knowledge_base.KnowledgeBaseSubAgent") as mock_cls,
            patch("rossum_agent.tools.subagents.knowledge_base._find_ranked_articles", return_value=[]),
            patch("rossum_agent.tools.subagents.knowledge_base._is_high_confidence_match", return_value=False),
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
        mock_result = SubAgentResult(
            analysis="Answer",
            input_tokens=50,
            output_tokens=25,
            iterations_used=1,
        )

        with (
            patch("rossum_agent.tools.subagents.knowledge_base.KnowledgeBaseSubAgent") as mock_cls,
            patch("rossum_agent.tools.subagents.knowledge_base._find_ranked_articles", return_value=[]),
            patch("rossum_agent.tools.subagents.knowledge_base._is_high_confidence_match", return_value=False),
        ):
            mock_instance = MagicMock()
            mock_instance.run.return_value = mock_result
            mock_cls.return_value = mock_instance

            search_knowledge_base("splitting", user_query="How do I configure document splitting?")

            call_args = mock_instance.run.call_args[0][0]
            assert "splitting" in call_args
            assert "How do I configure document splitting?" in call_args

    def test_user_query_same_as_query_not_duplicated(self):
        mock_result = SubAgentResult(
            analysis="Answer",
            input_tokens=50,
            output_tokens=25,
            iterations_used=1,
        )

        with (
            patch("rossum_agent.tools.subagents.knowledge_base.KnowledgeBaseSubAgent") as mock_cls,
            patch("rossum_agent.tools.subagents.knowledge_base._find_ranked_articles", return_value=[]),
            patch("rossum_agent.tools.subagents.knowledge_base._is_high_confidence_match", return_value=False),
        ):
            mock_instance = MagicMock()
            mock_instance.run.return_value = mock_result
            mock_cls.return_value = mock_instance

            search_knowledge_base("splitting", user_query="splitting")

            call_args = mock_instance.run.call_args[0][0]
            assert "Context" not in call_args

    def test_sub_agent_error_handled(self):
        with (
            patch(
                "rossum_agent.tools.subagents.knowledge_base.KnowledgeBaseSubAgent",
                side_effect=RuntimeError("Connection failed"),
            ),
            patch("rossum_agent.tools.subagents.knowledge_base._find_ranked_articles", return_value=[]),
            patch(
                "rossum_agent.tools.subagents.knowledge_base._is_high_confidence_match",
                return_value=False,
            ),
        ):
            result = search_knowledge_base("test query")

            parsed = json.loads(result)
            assert parsed["status"] == "error"
            assert "Sub-agent error" in parsed["message"]

    def test_no_tool_calls_omits_searches_key(self):
        mock_result = SubAgentResult(
            analysis="Direct answer",
            input_tokens=50,
            output_tokens=25,
            iterations_used=1,
            tool_calls=None,
        )

        with (
            patch("rossum_agent.tools.subagents.knowledge_base.KnowledgeBaseSubAgent") as mock_cls,
            patch("rossum_agent.tools.subagents.knowledge_base._find_ranked_articles", return_value=[]),
            patch("rossum_agent.tools.subagents.knowledge_base._is_high_confidence_match", return_value=False),
        ):
            mock_instance = MagicMock()
            mock_instance.run.return_value = mock_result
            mock_cls.return_value = mock_instance

            result = search_knowledge_base("test")

            parsed = json.loads(result)
            assert parsed["status"] == "success"
            assert "searches" not in parsed
