"""Check that serverless hook code follows TxScript conventions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rossum_agent.agent.models import ToolResultStep

from regression_tests.custom_checks._utils import call_haiku_check

if TYPE_CHECKING:
    from rossum_agent.agent.models import AgentStep

_PROMPT = """Analyze the following serverless hook code created by the agent.

Hook code:
{hook_code}

Does the code follow TxScript conventions? Check ALL of these:
1. Imports TxScript correctly (e.g., `from txscript import TxScript`)
2. Creates a TxScript instance via `TxScript.from_payload(payload)`
3. Accesses fields via `t.field.<name>` (not raw payload dict access)
4. Returns `t.hook_response()` at the end

Answer with a JSON object:
{{"passed": true/false, "reasoning": "Brief explanation of which conventions were followed or violated"}}"""


def _is_hook_tool(name: str, arguments: dict) -> bool:
    if name == "update_hook":
        return True
    if name != "create":
        return False
    data = arguments.get("data", {})
    return isinstance(data, dict) and data.get("entity") in ("hook", "hook_from_template")


def _get_args_dict(tc_arguments: dict | str) -> dict:
    return tc_arguments if isinstance(tc_arguments, dict) else {}


def check_serverless_hook_uses_txscript(
    steps: list[AgentStep], _api_base_url: str, _api_token: str
) -> tuple[bool, str]:
    """Verify created hook code follows TxScript syntax conventions.

    Searches tool results for create hook/hook_from_template calls and
    uses Haiku to semantically verify the hook code uses TxScript patterns.
    """
    for step in steps:
        if not isinstance(step, ToolResultStep):
            continue
        for tr in step.tool_results:
            tc = next((tc for tc in step.tool_calls if tc.id == tr.tool_call_id), None)
            if not tc or not _is_hook_tool(tc.name, _get_args_dict(tc.arguments)):
                continue

            content = tr.content if isinstance(tr.content, str) else str(tr.content)
            if content:
                return call_haiku_check(_PROMPT.format(hook_code=content[:8000]))

    for step in steps:
        if not isinstance(step, ToolResultStep):
            continue
        for tc in step.tool_calls:
            if not _is_hook_tool(tc.name, _get_args_dict(tc.arguments)):
                continue

            args = tc.arguments if isinstance(tc.arguments, str) else str(tc.arguments)
            if args:
                return call_haiku_check(_PROMPT.format(hook_code=args[:8000]))

    return False, "No create hook or update_hook tool call found"
