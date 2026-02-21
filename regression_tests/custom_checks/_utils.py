"""Shared utilities for custom checks."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from rossum_agent.agent.models import FinalAnswerStep, ToolResultStep
from rossum_agent.bedrock_client import HAIKU_MODEL_ID, create_bedrock_client
from rossum_api import SyncRossumAPIClient
from rossum_api.dtos import Token
from rossum_api.models.schema import Datapoint

if TYPE_CHECKING:
    from rossum_agent.agent.models import AgentStep
    from rossum_api.models.schema import Section


def extract_field_json_from_final_answer(final_answer: str, field_id: str) -> dict | None:
    """Extract a field's JSON config from the final answer markdown."""
    json_blocks = re.findall(r"```json\s*\n(.*?)\n```", final_answer, re.DOTALL)
    for block in json_blocks:
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("id") == field_id:
            return data
    return None


def call_haiku_check(prompt: str) -> tuple[bool, str]:
    """Call Haiku with a check prompt and parse the JSON response.

    Args:
        prompt: The fully formatted prompt to send to Haiku.

    Returns:
        Tuple of (passed, reasoning) from Haiku's response.
    """
    client = create_bedrock_client()
    response = client.messages.create(
        model=HAIKU_MODEL_ID, max_tokens=256, temperature=0, messages=[{"role": "user", "content": prompt}]
    )

    text = "".join(block.text for block in response.content if hasattr(block, "text"))

    try:
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            return result.get("passed", False), result.get("reasoning", text)
    except json.JSONDecodeError:
        pass

    return False, f"Could not parse LLM response: {text}"


def get_final_answer(steps: list[AgentStep]) -> str | None:
    """Extract most recent final answer from steps."""
    return next((s.final_answer for s in reversed(steps) if isinstance(s, FinalAnswerStep)), None)


def extract_id_from_final_answer(steps: list[AgentStep]) -> str | None:
    """Extract first numeric ID from most recent final answer."""
    final_answer = get_final_answer(steps)
    if final_answer:
        match = re.search(r"\b(\d+)\b", final_answer)
        if match:
            return match.group(1)
    return None


def agent_called_tool(steps: list[AgentStep], tool_name: str) -> bool:
    """Check if a tool was called in any step."""
    return any(tc.name == tool_name for step in steps if isinstance(step, ToolResultStep) for tc in step.tool_calls)


def count_tool_calls(steps: list[AgentStep], tool_name: str) -> int:
    """Count how many times a tool was called."""
    return sum(
        1 for step in steps if isinstance(step, ToolResultStep) for tc in step.tool_calls if tc.name == tool_name
    )


def create_api_client(api_base_url: str, api_token: str) -> SyncRossumAPIClient:
    """Create a sync API client."""
    return SyncRossumAPIClient(base_url=api_base_url, credentials=Token(api_token))


def extract_datapoints(schema_content: list[Section]) -> list[Datapoint]:
    """Traverse schema content and collect all leaf Datapoint nodes."""
    return [node for section in schema_content for node in section.traverse() if isinstance(node, Datapoint)]
