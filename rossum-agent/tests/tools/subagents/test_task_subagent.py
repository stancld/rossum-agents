"""Tests for rossum_agent.tools.subagents.task_subagent module."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

from rossum_agent.tools.core import AgentContext, set_context
from rossum_agent.tools.subagents.base import SubAgentResult
from rossum_agent.tools.subagents.task_subagent import (
    _EXCLUDED_TOOLS,
    TaskSubAgent,
    TaskSubAgentConfig,
    _build_task_prompt,
    _build_task_system_prompt,
    _snapshot_tools_for_task,
    execute_task,
)
from rossum_agent.tools.task_tracker import TaskStatus, TaskTracker


class TestTaskSubAgentConfig:
    """Test TaskSubAgentConfig dataclass."""

    def test_extends_subagent_config(self):
        config = TaskSubAgentConfig(
            tool_name="task_1",
            system_prompt="prompt",
            tools=[{"name": "tool1"}],
            internal_tool_names={"tool1"},
        )
        assert config.tool_name == "task_1"
        assert config.internal_tool_names == {"tool1"}

    def test_internal_tool_names_defaults_empty(self):
        config = TaskSubAgentConfig(
            tool_name="task_1",
            system_prompt="prompt",
            tools=[],
        )
        assert config.internal_tool_names == set()


class TestTaskSubAgent:
    """Test TaskSubAgent class."""

    def test_execute_tool_routes_internal(self):
        config = TaskSubAgentConfig(
            tool_name="task_1",
            system_prompt="prompt",
            tools=[],
            internal_tool_names={"write_file"},
        )
        agent = TaskSubAgent(config)

        with patch("rossum_agent.tools.execute_internal_tool", return_value="ok") as mock:
            result = agent.execute_tool("write_file", {"path": "test.txt", "content": "hello"})

            mock.assert_called_once_with("write_file", {"path": "test.txt", "content": "hello"})
            assert result == "ok"

    def test_execute_tool_routes_mcp(self):
        config = TaskSubAgentConfig(
            tool_name="task_1",
            system_prompt="prompt",
            tools=[],
            internal_tool_names=set(),
        )
        agent = TaskSubAgent(config)

        with patch("rossum_agent.tools.subagents.task_subagent.call_mcp_tool") as mock_mcp:
            mock_mcp.return_value = {"id": 123, "name": "Test"}
            result = agent.execute_tool("get_schema", {"schema_id": 123})

            mock_mcp.assert_called_once_with("get_schema", {"schema_id": 123})
            parsed = json.loads(result)
            assert parsed["id"] == 123

    def test_execute_tool_mcp_none_result(self):
        config = TaskSubAgentConfig(
            tool_name="task_1",
            system_prompt="prompt",
            tools=[],
            internal_tool_names=set(),
        )
        agent = TaskSubAgent(config)

        with patch("rossum_agent.tools.subagents.task_subagent.call_mcp_tool", return_value=None):
            result = agent.execute_tool("some_tool", {})
            assert result == "No data returned"

    def test_process_response_block_returns_none(self):
        config = TaskSubAgentConfig(
            tool_name="task_1",
            system_prompt="prompt",
            tools=[],
        )
        agent = TaskSubAgent(config)
        assert agent.process_response_block(MagicMock(), 1, 5) is None

    def test_run_completes_on_end_of_turn(self):
        config = TaskSubAgentConfig(
            tool_name="task_1",
            system_prompt="prompt",
            tools=[],
            internal_tool_names=set(),
        )
        agent = TaskSubAgent(config)

        mock_text_block = MagicMock()
        mock_text_block.text = "Task completed successfully"
        mock_text_block.type = "text"

        mock_response = MagicMock()
        mock_response.content = [mock_text_block]
        mock_response.stop_reason = "end_of_turn"
        mock_response.usage.input_tokens = 200
        mock_response.usage.output_tokens = 100
        mock_response.usage.cache_creation_input_tokens = 0
        mock_response.usage.cache_read_input_tokens = 0

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        set_context(AgentContext(progress_callback=MagicMock(), token_callback=MagicMock()))
        try:
            with patch("rossum_agent.tools.subagents.base.create_bedrock_client", return_value=mock_client):
                result = agent.run("Execute the task")
                assert result.analysis == "Task completed successfully"
                assert result.iterations_used == 1
        finally:
            set_context(AgentContext())


class TestBuildTaskSystemPrompt:
    """Test _build_task_system_prompt function."""

    def test_includes_domain_knowledge(self):
        prompt = _build_task_system_prompt()
        assert "Rossum" in prompt
        assert "Schema" in prompt

    def test_includes_task_instructions(self):
        prompt = _build_task_system_prompt()
        assert "single task" in prompt

    def test_excludes_task_tracking(self):
        prompt = _build_task_system_prompt()
        assert "create_task" not in prompt
        assert "update_task" not in prompt

    def test_excludes_orchestration_content(self):
        prompt = _build_task_system_prompt()
        assert "load_skill" not in prompt
        assert "load_tool_category" not in prompt
        assert "execute_task" not in prompt

    def test_includes_skill_contents(self):
        prompt = _build_task_system_prompt(skill_contents=["# Formula Fields\nUse formulas."])
        assert "# Formula Fields" in prompt
        assert "Use formulas." in prompt

    def test_without_skills(self):
        prompt_no_skills = _build_task_system_prompt()
        prompt_none = _build_task_system_prompt(skill_contents=None)
        prompt_empty = _build_task_system_prompt(skill_contents=[])
        assert prompt_no_skills == prompt_none == prompt_empty


class TestBuildTaskPrompt:
    """Test _build_task_prompt function."""

    def test_without_context(self):
        prompt = _build_task_prompt("Deploy schema", "Push schema to production", "")
        assert "## Task: Deploy schema" in prompt
        assert "Push schema to production" in prompt
        assert "Context" not in prompt

    def test_with_context(self):
        prompt = _build_task_prompt("Deploy schema", "Push changes", "Schema ID is 12345")
        assert "## Context from prior tasks" in prompt
        assert "Schema ID is 12345" in prompt
        assert "## Task: Deploy schema" in prompt


class TestSnapshotToolsForTask:
    """Test _snapshot_tools_for_task function."""

    def test_excludes_orchestration_tools(self):
        mock_internal = [
            {"name": "write_file"},
            {"name": "create_task"},
            {"name": "update_task"},
            {"name": "list_tasks"},
            {"name": "load_skill"},
            {"name": "load_tool_category"},
            {"name": "load_tool"},
            {"name": "ask_user_question"},
            {"name": "search_knowledge_base"},
        ]
        mock_dynamic = [
            {"name": "get_schema"},
            {"name": "list_tool_categories"},
        ]
        internal_names = {
            "write_file",
            "create_task",
            "update_task",
            "list_tasks",
            "load_skill",
            "load_tool_category",
            "load_tool",
            "ask_user_question",
            "search_knowledge_base",
        }

        with (
            patch("rossum_agent.tools.get_internal_tools", return_value=mock_internal),
            patch("rossum_agent.tools.get_internal_tool_names", return_value=internal_names),
            patch("rossum_agent.tools.dynamic_tools.get_dynamic_tools", return_value=mock_dynamic),
        ):
            tools, _names = _snapshot_tools_for_task()

        tool_names = {t["name"] for t in tools}
        for excluded in _EXCLUDED_TOOLS:
            assert excluded not in tool_names

        assert "write_file" in tool_names
        assert "search_knowledge_base" in tool_names
        assert "get_schema" in tool_names

    def test_extra_mcp_tools_included(self):
        mock_internal = [{"name": "write_file"}]
        mock_dynamic = [{"name": "get_queue"}]
        internal_names = {"write_file"}
        extra = [{"name": "get_schema"}, {"name": "create_schema_from_template"}]

        with (
            patch("rossum_agent.tools.get_internal_tools", return_value=mock_internal),
            patch("rossum_agent.tools.get_internal_tool_names", return_value=internal_names),
            patch("rossum_agent.tools.dynamic_tools.get_dynamic_tools", return_value=mock_dynamic),
        ):
            tools, _names = _snapshot_tools_for_task(extra_mcp_tools=extra)

        tool_names = {t["name"] for t in tools}
        assert "get_schema" in tool_names
        assert "create_schema_from_template" in tool_names
        assert "write_file" in tool_names
        assert "get_queue" in tool_names

    def test_extra_mcp_tools_deduplicated(self):
        mock_internal = [{"name": "write_file"}]
        mock_dynamic = [{"name": "get_schema"}]
        internal_names = {"write_file"}
        # get_schema already in dynamic tools — should not be duplicated
        extra = [{"name": "get_schema"}, {"name": "create_schema_from_template"}]

        with (
            patch("rossum_agent.tools.get_internal_tools", return_value=mock_internal),
            patch("rossum_agent.tools.get_internal_tool_names", return_value=internal_names),
            patch("rossum_agent.tools.dynamic_tools.get_dynamic_tools", return_value=mock_dynamic),
        ):
            tools, _names = _snapshot_tools_for_task(extra_mcp_tools=extra)

        tool_names = [t["name"] for t in tools]
        assert tool_names.count("get_schema") == 1
        assert "create_schema_from_template" in tool_names

    def test_extra_mcp_tools_excluded_tools_filtered(self):
        mock_internal = [{"name": "write_file"}]
        mock_dynamic = []
        internal_names = {"write_file"}
        # execute_task is in _EXCLUDED_TOOLS — should be filtered out
        extra = [{"name": "get_schema"}, {"name": "execute_task"}]

        with (
            patch("rossum_agent.tools.get_internal_tools", return_value=mock_internal),
            patch("rossum_agent.tools.get_internal_tool_names", return_value=internal_names),
            patch("rossum_agent.tools.dynamic_tools.get_dynamic_tools", return_value=mock_dynamic),
        ):
            tools, _names = _snapshot_tools_for_task(extra_mcp_tools=extra)

        tool_names = {t["name"] for t in tools}
        assert "get_schema" in tool_names
        assert "execute_task" not in tool_names

    def test_internal_names_only_include_actual_internals(self):
        mock_internal = [
            {"name": "write_file"},
            {"name": "search_knowledge_base"},
        ]
        mock_dynamic = [
            {"name": "get_schema"},
        ]
        internal_names = {"write_file", "search_knowledge_base"}

        with (
            patch("rossum_agent.tools.get_internal_tools", return_value=mock_internal),
            patch("rossum_agent.tools.get_internal_tool_names", return_value=internal_names),
            patch("rossum_agent.tools.dynamic_tools.get_dynamic_tools", return_value=mock_dynamic),
        ):
            _tools, names = _snapshot_tools_for_task()

        assert "write_file" in names
        assert "search_knowledge_base" in names
        assert "get_schema" not in names


class TestExecuteTask:
    """Test execute_task tool function."""

    def test_no_tracker_returns_error(self):
        set_context(AgentContext(task_tracker=None))
        try:
            result = execute_task(task_id="1")
            parsed = json.loads(result)
            assert "error" in parsed
            assert "not available" in parsed["error"]
        finally:
            set_context(AgentContext())

    def test_missing_task_returns_error(self):
        tracker = TaskTracker()
        set_context(AgentContext(task_tracker=tracker))
        try:
            result = execute_task(task_id="999")
            parsed = json.loads(result)
            assert "error" in parsed
            assert "not found" in parsed["error"]
        finally:
            set_context(AgentContext())

    def test_successful_execution(self):
        tracker = TaskTracker()
        task = tracker.create_task("Test task", "Do something")

        mock_result = SubAgentResult(
            analysis="Task completed: created schema ID 123",
            input_tokens=500,
            output_tokens=200,
            iterations_used=2,
        )

        set_context(
            AgentContext(
                task_tracker=tracker,
                progress_callback=MagicMock(),
                token_callback=MagicMock(),
                task_snapshot_callback=MagicMock(),
            )
        )
        try:
            with (
                patch(
                    "rossum_agent.tools.subagents.task_subagent._snapshot_tools_for_task",
                    return_value=([{"name": "get_schema"}], set()),
                ),
                patch.object(TaskSubAgent, "run", return_value=mock_result),
            ):
                result = execute_task(task_id=task.id)
                parsed = json.loads(result)

                assert parsed["task_id"] == task.id
                assert parsed["subject"] == "Test task"
                assert "schema ID 123" in parsed["analysis"]
                assert parsed["is_error"] is False
                assert parsed["iterations_used"] == 2
                assert parsed["input_tokens"] == 500
                assert parsed["output_tokens"] == 200
                assert "elapsed_ms" in parsed
        finally:
            set_context(AgentContext())

    def test_updates_task_status(self):
        tracker = TaskTracker()
        task = tracker.create_task("Test task", "Do something")
        snapshot_calls = []

        mock_result = SubAgentResult(
            analysis="Done",
            input_tokens=100,
            output_tokens=50,
            iterations_used=1,
        )

        set_context(
            AgentContext(
                task_tracker=tracker,
                progress_callback=MagicMock(),
                token_callback=MagicMock(),
                task_snapshot_callback=lambda s: snapshot_calls.append(s),
            )
        )
        try:
            with (
                patch(
                    "rossum_agent.tools.subagents.task_subagent._snapshot_tools_for_task",
                    return_value=([{"name": "tool"}], set()),
                ),
                patch.object(TaskSubAgent, "run", return_value=mock_result),
            ):
                execute_task(task_id=task.id)

                assert task.status == TaskStatus.completed
                assert len(snapshot_calls) == 2  # in_progress + completed
        finally:
            set_context(AgentContext())

    def test_no_tools_returns_error(self):
        tracker = TaskTracker()
        task = tracker.create_task("Test task", "Do something")

        set_context(
            AgentContext(
                task_tracker=tracker,
                task_snapshot_callback=MagicMock(),
            )
        )
        try:
            with patch(
                "rossum_agent.tools.subagents.task_subagent._snapshot_tools_for_task",
                return_value=([], set()),
            ):
                result = execute_task(task_id=task.id)
                parsed = json.loads(result)
                assert "error" in parsed
                assert "No tools" in parsed["error"]
        finally:
            set_context(AgentContext())

    def test_context_passed_to_subagent(self):
        tracker = TaskTracker()
        task = tracker.create_task("Deploy", "Deploy schema")

        mock_result = SubAgentResult(
            analysis="Deployed",
            input_tokens=100,
            output_tokens=50,
            iterations_used=1,
        )

        run_calls = []

        def capture_run(self, message):
            run_calls.append(message)
            return mock_result

        set_context(
            AgentContext(
                task_tracker=tracker,
                progress_callback=MagicMock(),
                token_callback=MagicMock(),
                task_snapshot_callback=MagicMock(),
            )
        )
        try:
            with (
                patch(
                    "rossum_agent.tools.subagents.task_subagent._snapshot_tools_for_task",
                    return_value=([{"name": "tool"}], set()),
                ),
                patch.object(TaskSubAgent, "run", capture_run),
            ):
                execute_task(task_id=task.id, context="Schema ID: 123")

                assert len(run_calls) == 1
                assert "Schema ID: 123" in run_calls[0]
                assert "Deploy schema" in run_calls[0]
        finally:
            set_context(AgentContext())

    def test_error_resets_task_to_pending(self):
        tracker = TaskTracker()
        task = tracker.create_task("Failing task", "This will fail")

        mock_result = SubAgentResult(
            analysis="Error calling Opus sub-agent: AWS connection failed",
            input_tokens=100,
            output_tokens=0,
            iterations_used=0,
        )

        set_context(
            AgentContext(
                task_tracker=tracker,
                progress_callback=MagicMock(),
                token_callback=MagicMock(),
                task_snapshot_callback=MagicMock(),
            )
        )
        try:
            with (
                patch(
                    "rossum_agent.tools.subagents.task_subagent._snapshot_tools_for_task",
                    return_value=([{"name": "tool"}], set()),
                ),
                patch.object(TaskSubAgent, "run", return_value=mock_result),
            ):
                result = execute_task(task_id=task.id)
                parsed = json.loads(result)

                assert parsed["is_error"] is True
                assert task.status == TaskStatus.pending
        finally:
            set_context(AgentContext())

    def test_elapsed_ms_measured(self):
        tracker = TaskTracker()
        task = tracker.create_task("Test", "Test task")

        mock_result = SubAgentResult(
            analysis="Done",
            input_tokens=100,
            output_tokens=50,
            iterations_used=1,
        )

        set_context(
            AgentContext(
                task_tracker=tracker,
                progress_callback=MagicMock(),
                token_callback=MagicMock(),
                task_snapshot_callback=MagicMock(),
            )
        )
        try:
            with (
                patch(
                    "rossum_agent.tools.subagents.task_subagent._snapshot_tools_for_task",
                    return_value=([{"name": "tool"}], set()),
                ),
                patch.object(TaskSubAgent, "run", return_value=mock_result),
            ):
                result = execute_task(task_id=task.id)
                parsed = json.loads(result)

                assert isinstance(parsed["elapsed_ms"], float)
                assert parsed["elapsed_ms"] >= 0
        finally:
            set_context(AgentContext())

    def test_skills_marks_loaded_and_injects_content(self):
        tracker = TaskTracker()
        task = tracker.create_task("Add formula", "Create formula field")

        @dataclass
        class FakeSkill:
            name: str
            content: str
            file_path: Path = Path("fake.md")

        mock_skill = FakeSkill(name="Formula Fields", content="# Formula Fields\nUse TxScript.")
        mock_result = SubAgentResult(
            analysis="Done",
            input_tokens=100,
            output_tokens=50,
            iterations_used=1,
        )

        captured_configs: list[TaskSubAgentConfig] = []
        original_init = TaskSubAgent.__init__

        def capture_init(self, config):
            captured_configs.append(config)
            original_init(self, config)

        set_context(
            AgentContext(
                task_tracker=tracker,
                progress_callback=MagicMock(),
                token_callback=MagicMock(),
                task_snapshot_callback=MagicMock(),
            )
        )
        try:
            with (
                patch(
                    "rossum_agent.tools.subagents.task_subagent.get_skill",
                    return_value=mock_skill,
                ) as mock_get,
                patch(
                    "rossum_agent.tools.subagents.task_subagent.is_skill_loaded",
                    return_value=False,
                ),
                patch(
                    "rossum_agent.tools.dynamic_tools.mark_skill_loaded",
                ) as mock_mark,
                patch(
                    "rossum_agent.tools.dynamic_tools.unmark_skill_loaded",
                ) as mock_unmark,
                patch(
                    "rossum_agent.tools.subagents.task_subagent._snapshot_tools_for_task",
                    return_value=([{"name": "tool"}], set()),
                ),
                patch.object(TaskSubAgent, "__init__", capture_init),
                patch.object(TaskSubAgent, "run", return_value=mock_result),
            ):
                execute_task(task_id=task.id, skills=["formula-fields"])

                mock_get.assert_called_once_with("formula-fields")
                mock_mark.assert_called_once_with("formula-fields")
                mock_unmark.assert_called_once_with("formula-fields")
                assert len(captured_configs) == 1
                assert "# Formula Fields" in captured_configs[0].system_prompt
                assert "Use TxScript." in captured_configs[0].system_prompt
        finally:
            set_context(AgentContext())

    def test_skills_loaded_before_snapshot_and_cleaned_up_after(self):
        tracker = TaskTracker()
        task = tracker.create_task("Add formula", "Create formula field")

        @dataclass
        class FakeSkill:
            name: str
            content: str
            file_path: Path = Path("fake.md")

        call_order: list[str] = []

        def track_mark(slug):
            call_order.append("mark_skill_loaded")

        def track_snapshot(**kwargs):
            call_order.append("snapshot_tools")
            return [{"name": "tool"}], set()

        def track_unmark(slug):
            call_order.append("unmark_skill_loaded")

        mock_result = SubAgentResult(
            analysis="Done",
            input_tokens=100,
            output_tokens=50,
            iterations_used=1,
        )

        set_context(
            AgentContext(
                task_tracker=tracker,
                progress_callback=MagicMock(),
                token_callback=MagicMock(),
                task_snapshot_callback=MagicMock(),
            )
        )
        try:
            with (
                patch(
                    "rossum_agent.tools.subagents.task_subagent.get_skill",
                    return_value=FakeSkill(name="Formula Fields", content="content"),
                ),
                patch(
                    "rossum_agent.tools.subagents.task_subagent.is_skill_loaded",
                    return_value=False,
                ),
                patch(
                    "rossum_agent.tools.dynamic_tools.mark_skill_loaded",
                    side_effect=track_mark,
                ),
                patch(
                    "rossum_agent.tools.dynamic_tools.unmark_skill_loaded",
                    side_effect=track_unmark,
                ),
                patch(
                    "rossum_agent.tools.subagents.task_subagent._snapshot_tools_for_task",
                    side_effect=track_snapshot,
                ),
                patch.object(TaskSubAgent, "run", return_value=mock_result),
            ):
                execute_task(task_id=task.id, skills=["formula-fields"])

                assert call_order == ["mark_skill_loaded", "snapshot_tools", "unmark_skill_loaded"]
        finally:
            set_context(AgentContext())

    def test_unknown_skill_skipped(self):
        tracker = TaskTracker()
        task = tracker.create_task("Test", "Test task")

        mock_result = SubAgentResult(
            analysis="Done",
            input_tokens=100,
            output_tokens=50,
            iterations_used=1,
        )

        captured_configs: list[TaskSubAgentConfig] = []
        original_init = TaskSubAgent.__init__

        def capture_init(self, config):
            captured_configs.append(config)
            original_init(self, config)

        set_context(
            AgentContext(
                task_tracker=tracker,
                progress_callback=MagicMock(),
                token_callback=MagicMock(),
                task_snapshot_callback=MagicMock(),
            )
        )
        try:
            with (
                patch(
                    "rossum_agent.tools.subagents.task_subagent.get_skill",
                    return_value=None,
                ),
                patch(
                    "rossum_agent.tools.dynamic_tools.mark_skill_loaded",
                ) as mock_mark,
                patch(
                    "rossum_agent.tools.dynamic_tools.unmark_skill_loaded",
                ) as mock_unmark,
                patch(
                    "rossum_agent.tools.subagents.task_subagent._snapshot_tools_for_task",
                    return_value=([{"name": "tool"}], set()),
                ),
                patch.object(TaskSubAgent, "__init__", capture_init),
                patch.object(TaskSubAgent, "run", return_value=mock_result),
            ):
                result = execute_task(task_id=task.id, skills=["nonexistent-skill"])
                parsed = json.loads(result)

                assert parsed["is_error"] is False
                mock_mark.assert_not_called()
                mock_unmark.assert_not_called()
                # Prompt should not contain skill content
                prompt_without_skills = _build_task_system_prompt()
                assert captured_configs[0].system_prompt == prompt_without_skills
        finally:
            set_context(AgentContext())

    def test_already_loaded_skill_not_unmarked(self):
        """Skills already loaded by the main agent should not be unmarked after task."""
        tracker = TaskTracker()
        task = tracker.create_task("Add formula", "Create formula field")

        @dataclass
        class FakeSkill:
            name: str
            content: str
            file_path: Path = Path("fake.md")

        mock_result = SubAgentResult(
            analysis="Done",
            input_tokens=100,
            output_tokens=50,
            iterations_used=1,
        )

        set_context(
            AgentContext(
                task_tracker=tracker,
                progress_callback=MagicMock(),
                token_callback=MagicMock(),
                task_snapshot_callback=MagicMock(),
            )
        )
        try:
            with (
                patch(
                    "rossum_agent.tools.subagents.task_subagent.get_skill",
                    return_value=FakeSkill(name="Formula Fields", content="content"),
                ),
                patch(
                    "rossum_agent.tools.subagents.task_subagent.is_skill_loaded",
                    return_value=True,
                ),
                patch(
                    "rossum_agent.tools.dynamic_tools.mark_skill_loaded",
                ) as mock_mark,
                patch(
                    "rossum_agent.tools.dynamic_tools.unmark_skill_loaded",
                ) as mock_unmark,
                patch(
                    "rossum_agent.tools.subagents.task_subagent._snapshot_tools_for_task",
                    return_value=([{"name": "tool"}], set()),
                ),
                patch.object(TaskSubAgent, "run", return_value=mock_result),
            ):
                execute_task(task_id=task.id, skills=["formula-fields"])

                # Already loaded — should not be marked or unmarked
                mock_mark.assert_not_called()
                mock_unmark.assert_not_called()
        finally:
            set_context(AgentContext())

    def test_tool_categories_fetched_transiently(self):
        """tool_categories should fetch MCP tools without adding to main agent."""
        tracker = TaskTracker()
        task = tracker.create_task("Create schema", "Build a schema")

        mock_result = SubAgentResult(
            analysis="Done",
            input_tokens=100,
            output_tokens=50,
            iterations_used=1,
        )

        extra_tools = [{"name": "get_schema"}, {"name": "create_schema_from_template"}]

        set_context(
            AgentContext(
                task_tracker=tracker,
                progress_callback=MagicMock(),
                token_callback=MagicMock(),
                task_snapshot_callback=MagicMock(),
            )
        )
        try:
            with (
                patch(
                    "rossum_agent.tools.dynamic_tools.fetch_category_tools",
                    return_value=extra_tools,
                ) as mock_fetch,
                patch(
                    "rossum_agent.tools.subagents.task_subagent._snapshot_tools_for_task",
                    return_value=(
                        [{"name": "write_file"}, {"name": "get_schema"}, {"name": "create_schema_from_template"}],
                        set(),
                    ),
                ) as mock_snapshot,
                patch.object(TaskSubAgent, "run", return_value=mock_result),
            ):
                execute_task(task_id=task.id, tool_categories=["schemas"])

                mock_fetch.assert_called_once_with(["schemas"])
                # Extra tools passed to snapshot
                mock_snapshot.assert_called_once_with(extra_mcp_tools=extra_tools)
        finally:
            set_context(AgentContext())

    def test_tool_categories_and_skills_combined(self):
        """Both skills and tool_categories can be used together."""
        tracker = TaskTracker()
        task = tracker.create_task("Add formula", "Create formula field on schema")

        @dataclass
        class FakeSkill:
            name: str
            content: str
            file_path: Path = Path("fake.md")

        mock_result = SubAgentResult(
            analysis="Done",
            input_tokens=100,
            output_tokens=50,
            iterations_used=1,
        )

        extra_tools = [{"name": "get_schema"}]

        set_context(
            AgentContext(
                task_tracker=tracker,
                progress_callback=MagicMock(),
                token_callback=MagicMock(),
                task_snapshot_callback=MagicMock(),
            )
        )
        try:
            with (
                patch(
                    "rossum_agent.tools.subagents.task_subagent.get_skill",
                    return_value=FakeSkill(name="Formula Fields", content="# Formula"),
                ),
                patch(
                    "rossum_agent.tools.subagents.task_subagent.is_skill_loaded",
                    return_value=False,
                ),
                patch("rossum_agent.tools.dynamic_tools.mark_skill_loaded"),
                patch("rossum_agent.tools.dynamic_tools.unmark_skill_loaded"),
                patch(
                    "rossum_agent.tools.dynamic_tools.fetch_category_tools",
                    return_value=extra_tools,
                ),
                patch(
                    "rossum_agent.tools.subagents.task_subagent._snapshot_tools_for_task",
                    return_value=([{"name": "tool"}], set()),
                ) as mock_snapshot,
                patch.object(TaskSubAgent, "run", return_value=mock_result),
            ):
                result = execute_task(
                    task_id=task.id,
                    skills=["formula-fields"],
                    tool_categories=["schemas"],
                )
                parsed = json.loads(result)

                assert parsed["is_error"] is False
                mock_snapshot.assert_called_once_with(extra_mcp_tools=extra_tools)
        finally:
            set_context(AgentContext())
