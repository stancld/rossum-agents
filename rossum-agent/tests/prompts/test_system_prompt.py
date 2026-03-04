from __future__ import annotations

from rossum_agent.prompts.system_prompt import get_system_prompt


class TestSystemPromptPersona:
    def test_includes_default_persona_block(self):
        prompt = get_system_prompt("default")
        assert "# Persona: default" in prompt
        assert "# Persona: cautious" not in prompt

    def test_includes_cautious_persona_block(self):
        prompt = get_system_prompt("cautious")
        assert "# Persona: cautious" in prompt
        assert "# Persona: default" not in prompt


class TestSystemPromptTaskTracking:
    def test_execute_task_manages_status_automatically(self):
        prompt = get_system_prompt("default")
        assert "execute_task" in prompt
        assert "`in_progress` → `completed`" in prompt

    def test_discourages_manual_update_task_for_subagent_tasks(self):
        prompt = get_system_prompt("default")
        assert "do not call `update_task` for tasks executed via sub-agents" in prompt
