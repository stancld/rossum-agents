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
    def test_requires_update_task_transitions(self):
        prompt = get_system_prompt("default")
        assert 'update_task(status="in_progress")' in prompt
        assert 'update_task(status="completed")' in prompt

    def test_does_not_forbid_update_task(self):
        prompt = get_system_prompt("default")
        assert "Do not call `update_task`" not in prompt
