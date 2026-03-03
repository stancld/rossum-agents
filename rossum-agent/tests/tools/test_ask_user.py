"""Tests for rossum_agent.tools.ask_user module."""

from __future__ import annotations

import json

from rossum_agent.tools.ask_user import ask_user_question, get_ask_user_question_definition
from rossum_agent.tools.core import AgentContext, AgentQuestion, set_context


class TestGetAskUserQuestionDefinition:
    """Tests for the tool definition."""

    def test_definition_has_required_fields(self) -> None:
        defn = get_ask_user_question_definition()
        assert defn["name"] == "ask_user_question"
        assert "description" in defn
        assert "input_schema" in defn

    def test_definition_schema_structure(self) -> None:
        defn = get_ask_user_question_definition()
        schema = defn["input_schema"]
        assert schema["type"] == "object"
        assert "question" in schema["properties"]
        assert "options" in schema["properties"]
        assert "multi_select" in schema["properties"]
        assert "questions" in schema["properties"]

    def test_options_schema_has_value_and_label_required(self) -> None:
        defn = get_ask_user_question_definition()
        options_schema = defn["input_schema"]["properties"]["options"]
        assert options_schema["type"] == "array"
        item_schema = options_schema["items"]
        assert "value" in item_schema["properties"]
        assert "label" in item_schema["properties"]
        assert "description" in item_schema["properties"]
        assert item_schema["required"] == ["value", "label"]

    def test_questions_array_schema(self) -> None:
        defn = get_ask_user_question_definition()
        questions_schema = defn["input_schema"]["properties"]["questions"]
        assert questions_schema["type"] == "array"
        item_schema = questions_schema["items"]
        assert "question" in item_schema["properties"]
        assert "options" in item_schema["properties"]
        assert "multi_select" in item_schema["properties"]
        assert item_schema["required"] == ["question"]


class TestAskUserQuestionSingleFormat:
    """Tests for the single-question format (backward compat)."""

    def test_free_text_question(self) -> None:
        set_context(AgentContext())
        try:
            result = json.loads(ask_user_question("What queue should I use?"))
            assert result["status"] == "question_sent"
            assert result["question"] == "What queue should I use?"
            assert result["question_count"] == 1
            assert "option_count" not in result
        finally:
            set_context(AgentContext())

    def test_question_with_options(self) -> None:
        set_context(AgentContext())
        try:
            options = [
                {"value": "a", "label": "Option A", "description": "First option"},
                {"value": "b", "label": "Option B"},
            ]
            result = json.loads(ask_user_question("Pick one", options=options))
            assert result["status"] == "question_sent"
            assert result["option_count"] == 2
            assert result["question_count"] == 1
        finally:
            set_context(AgentContext())

    def test_multi_select(self) -> None:
        set_context(AgentContext())
        try:
            options = [
                {"value": "x", "label": "X"},
                {"value": "y", "label": "Y"},
            ]
            result = json.loads(ask_user_question("Pick many", options=options, multi_select=True))
            assert result["status"] == "question_sent"
        finally:
            set_context(AgentContext())

    def test_callback_is_called_with_correct_data(self) -> None:
        captured: list[AgentQuestion] = []
        ctx = AgentContext(question_callback=lambda q: captured.append(q))
        set_context(ctx)
        try:
            options = [
                {"value": "a", "label": "Alpha", "description": "First"},
                {"value": "b", "label": "Beta"},
            ]
            ask_user_question("Choose one", options=options, multi_select=False)

            assert len(captured) == 1
            q = captured[0]
            assert len(q.questions) == 1
            item = q.questions[0]
            assert item.question == "Choose one"
            assert len(item.options) == 2
            assert item.options[0].value == "a"
            assert item.options[0].label == "Alpha"
            assert item.options[0].description == "First"
            assert item.options[1].value == "b"
            assert item.options[1].description == ""
            assert item.multi_select is False
        finally:
            set_context(AgentContext())

    def test_callback_not_called_when_none(self) -> None:
        """No crash when callback is None."""
        set_context(AgentContext(question_callback=None))
        try:
            result = json.loads(ask_user_question("Hello?"))
            assert result["status"] == "question_sent"
        finally:
            set_context(AgentContext())

    def test_description_truncated_at_90_chars(self) -> None:
        captured: list[AgentQuestion] = []
        ctx = AgentContext(question_callback=lambda q: captured.append(q))
        set_context(ctx)
        try:
            long_desc = "A" * 200
            options = [{"value": "x", "label": "X", "description": long_desc}]
            ask_user_question("Q?", options=options)

            assert len(captured[0].questions[0].options[0].description) == 90
        finally:
            set_context(AgentContext())

    def test_empty_options_list(self) -> None:
        """Empty options list treated like no options."""
        set_context(AgentContext())
        try:
            result = json.loads(ask_user_question("Q?", options=[]))
            assert result["status"] == "question_sent"
            assert "option_count" not in result
        finally:
            set_context(AgentContext())


class TestAskUserQuestionMultiFormat:
    """Tests for the multi-question format."""

    def test_multiple_questions(self) -> None:
        set_context(AgentContext())
        try:
            questions = [
                {"question": "What name?"},
                {"question": "Which workspace?", "options": [{"value": "ws1", "label": "WS 1"}]},
                {"question": "Which template?", "options": [{"value": "t1", "label": "T1"}], "multi_select": True},
            ]
            result = json.loads(ask_user_question(questions=questions))
            assert result["status"] == "question_sent"
            assert result["question_count"] == 3
            # No single-question fields when count > 1
            assert "question" not in result
            assert "option_count" not in result
        finally:
            set_context(AgentContext())

    def test_multi_question_callback_data(self) -> None:
        captured: list[AgentQuestion] = []
        ctx = AgentContext(question_callback=lambda q: captured.append(q))
        set_context(ctx)
        try:
            questions = [
                {"question": "Name?"},
                {"question": "Pick one", "options": [{"value": "a", "label": "A"}]},
            ]
            ask_user_question(questions=questions)

            assert len(captured) == 1
            q = captured[0]
            assert len(q.questions) == 2
            assert q.questions[0].question == "Name?"
            assert q.questions[0].options == []
            assert q.questions[0].multi_select is False
            assert q.questions[1].question == "Pick one"
            assert len(q.questions[1].options) == 1
        finally:
            set_context(AgentContext())

    def test_questions_array_takes_precedence(self) -> None:
        """When both question and questions are provided, questions wins."""
        captured: list[AgentQuestion] = []
        ctx = AgentContext(question_callback=lambda q: captured.append(q))
        set_context(ctx)
        try:
            ask_user_question(
                question="ignored",
                questions=[{"question": "Real Q1"}, {"question": "Real Q2"}],
            )
            assert len(captured[0].questions) == 2
            assert captured[0].questions[0].question == "Real Q1"
        finally:
            set_context(AgentContext())

    def test_single_item_questions_array(self) -> None:
        """Single-item questions array returns single-question result format."""
        set_context(AgentContext())
        try:
            result = json.loads(ask_user_question(questions=[{"question": "Solo?"}]))
            assert result["question_count"] == 1
            assert result["question"] == "Solo?"
        finally:
            set_context(AgentContext())

    def test_description_truncated_in_questions_array(self) -> None:
        captured: list[AgentQuestion] = []
        ctx = AgentContext(question_callback=lambda q: captured.append(q))
        set_context(ctx)
        try:
            long_desc = "B" * 200
            questions = [
                {"question": "Q?", "options": [{"value": "x", "label": "X", "description": long_desc}]},
            ]
            ask_user_question(questions=questions)
            assert len(captured[0].questions[0].options[0].description) == 90
        finally:
            set_context(AgentContext())
