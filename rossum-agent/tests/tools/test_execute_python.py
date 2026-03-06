"""Tests for the execute_python tool."""

from __future__ import annotations

import json
from unittest.mock import patch

from rossum_agent.tools.python_exec import execute_python, get_execute_python_definition


class TestGetExecPythonDefinition:
    def test_contains_expected_fields(self) -> None:
        definition = get_execute_python_definition()

        assert definition["name"] == "execute_python"
        assert "description" in definition
        assert definition["input_schema"]["required"] == ["code"]

    def test_does_not_list_helper_functions(self) -> None:
        definition = get_execute_python_definition()

        assert "schema_content(value)" not in definition["description"]
        assert "suggest_formula_field" not in definition["description"]
        assert "prefer `write_file(...)` inside the snippet" in definition["description"]
        assert "Load the relevant skill first" in definition["description"]


class TestExecPython:
    def test_returns_last_expression(self) -> None:
        result = execute_python(code="1 + 2")
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        assert parsed["result"] == 3

    def test_prefers_result_variable_when_no_last_expression(self) -> None:
        result = execute_python(code="x = 2\nresult = x + 5")
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        assert parsed["result"] == 7

    def test_captures_stdout(self) -> None:
        result = execute_python(code='print("hello")\nresult = "ok"')
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        assert parsed["result"] == "ok"
        assert parsed["stdout"] == "hello\n"

    @patch("rossum_agent.tools.python_exec._suggest_rule")
    def test_exposes_rule_helper(self, mock_suggest_rule) -> None:
        mock_suggest_rule.return_value = json.dumps(
            {"status": "success", "name": "Rule", "trigger_condition": "field.amount_total > 0", "actions": []}
        )

        result = execute_python(
            code='result = suggest_rule(user_query="Check total", queue_id=123)',
            operation_name="suggest rule",
        )
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        assert parsed["operation_name"] == "suggest rule"
        assert parsed["result"]["name"] == "Rule"
        mock_suggest_rule.assert_called_once_with(user_query="Check total", queue_id=123)

    @patch("rossum_agent.tools.python_exec._suggest_formula_field")
    def test_exposes_copilot_namespace(self, mock_suggest_formula_field) -> None:
        mock_suggest_formula_field.return_value = json.dumps({"status": "success", "formula": "field.amount_total"})

        result = execute_python(
            code=(
                "result = copilot.suggest_formula_field("
                'label="Amount Copy", hint="Copy amount", schema_id=1, section_id="header"'
                ")"
            )
        )
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        assert parsed["result"]["formula"] == "field.amount_total"

    @patch("rossum_agent.tools.python_exec._call_mcp_tool")
    def test_exposes_api_get_helper(self, mock_call_mcp_tool) -> None:
        mock_call_mcp_tool.return_value = {"content": [{"id": "header"}]}

        result = execute_python(code='result = api_get("schema", 123)')
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        assert parsed["result"] == {"content": [{"id": "header"}]}
        mock_call_mcp_tool.assert_called_once_with("get", {"entity": "schema", "entity_id": 123})

    def test_rejects_try_star(self) -> None:
        result = execute_python(code="try:\n  pass\nexcept* ValueError:\n  pass")
        parsed = json.loads(result)

        assert parsed["status"] == "error"
        assert "TryStar" in parsed["error"]

    def test_rejects_imports(self) -> None:
        result = execute_python(code="import os\nresult = 1")
        parsed = json.loads(result)

        assert parsed["status"] == "error"
        assert "Import" in parsed["error"]

    def test_rejects_dunder_attribute_access(self) -> None:
        result = execute_python(code="result = copilot.__class__")
        parsed = json.loads(result)

        assert parsed["status"] == "error"
        assert "Attributes starting with '__'" in parsed["error"]

    def test_schema_content_accepts_full_schema_object(self) -> None:
        result = execute_python(
            code=(
                'schema = {"id": 123, "content": [{"id": "header", "category": "section", "children": []}]}\n'
                "result = schema_content(schema)"
            )
        )
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        assert parsed["result"] == [{"id": "header", "category": "section", "children": []}]

    def test_schema_content_accepts_unified_get_response(self) -> None:
        result = execute_python(
            code=(
                'schema = {"entity": "schema", "id": 123, "data": {"content": [{"id": "header"}]}}\n'
                "result = schema_content(schema)"
            )
        )
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        assert parsed["result"] == [{"id": "header"}]

    def test_schema_content_accepts_bare_content_array(self) -> None:
        result = execute_python(code='result = schema_content([{"id": "header"}])')
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        assert parsed["result"] == [{"id": "header"}]

    def test_schema_content_rejects_non_schema_payload(self) -> None:
        result = execute_python(code='result = schema_content({"id": 123})')
        parsed = json.loads(result)

        assert parsed["status"] == "error"
        assert "schema_content()" in parsed["error"]

    def test_execute_python_alias_matches_execute_python(self) -> None:
        assert json.loads(execute_python(code="1 + 2"))["result"] == 3
