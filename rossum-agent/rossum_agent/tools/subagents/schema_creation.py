"""Schema creation sub-agent.

Provides guided schema creation with full structure validation. The workflow:
1. LLM analyzes user requirements for sections, datapoints, multivalues, tuples
2. Builds complete schema content structure
3. Single POST to create schema
"""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

from anthropic import beta_tool

from rossum_agent.tools.subagents.base import (
    SubAgent,
    SubAgentConfig,
    SubAgentResult,
)
from rossum_agent.tools.subagents.mcp_helpers import call_mcp_tool

logger = logging.getLogger(__name__)

_SCHEMA_CREATION_SYSTEM_PROMPT = """Goal: Create a complete schema matching user requirements.

## Content Structure

Schema content is a list of **sections**. Each section contains datapoints, multivalues, or tuples.

### Hierarchy

```
content: [
  section → children: [
    datapoint (simple field)
    multivalue → children: {
      datapoint (list field) OR
      tuple → children: [datapoint, datapoint, ...] (table)
    }
  ]
]
```

### Section

| Field | Required | Description |
|-------|----------|-------------|
| id | Yes | Unique ID (≤50 chars, lowercase, underscores) |
| label | Yes | Display name |
| category | Yes | Must be "section" |
| children | Yes | List of datapoints or multivalues |

### Datapoint

| Field | Required | Description |
|-------|----------|-------------|
| id | Yes | Unique ID |
| label | Yes | Display name |
| category | Yes | Must be "datapoint" |
| type | Yes | string, number, date, enum, button |

Optional: rir_field_names, default_value, hidden, disable_prediction, can_export, constraints, options (for enum), ui_configuration, width

### Multivalue (Lists/Tables)

| Field | Required | Description |
|-------|----------|-------------|
| id | Yes | Unique ID |
| label | Yes | Display name |
| category | Yes | Must be "multivalue" |
| children | Yes | Single datapoint OR tuple object (NOT a list) |

Optional: rir_field_names (e.g., ["line_items"]), min_occurrences, max_occurrences

### Tuple (Table Row)

| Field | Required | Description |
|-------|----------|-------------|
| id | Yes | Unique ID |
| label | Yes | Display name |
| category | Yes | Must be "tuple" |
| children | Yes | List of datapoint objects (columns) |

## Constraints

- Field `id` must be valid identifier (lowercase, underscores, no spaces)
- Do NOT set `rir_field_names` unless user explicitly provides engine field names
- `ui_configuration.type`: captured, data, manual, formula, reasoning
- `ui_configuration.edit`: enabled, enabled_without_warning, disabled

## Common rir_field_names

| Field Type | Values |
|------------|--------|
| Invoice ID | invoice_id, document_id |
| Date | date_issue, date_due |
| Amount | amount_total, amount_due, amount_total_tax |
| Vendor | sender_name, sender_address, sender_vat_id |
| Line Items | line_items (multivalue) |
| Item fields | item_description, item_quantity, item_amount_total |

Return: Summary of created schema structure."""

_CREATE_SCHEMA_TOOL: dict[str, Any] = {
    "name": "create_schema",
    "description": "Create a new schema with full content structure.",
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Schema name"},
            "content": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "label": {"type": "string"},
                        "category": {"type": "string", "enum": ["section"]},
                        "hidden": {"type": "boolean"},
                        "children": {"type": "array"},
                    },
                    "required": ["id", "label", "category", "children"],
                },
                "description": "List of section objects with nested datapoints/multivalues",
            },
        },
        "required": ["name", "content"],
    },
}

_OPUS_TOOLS: list[dict[str, Any]] = [_CREATE_SCHEMA_TOOL]


def _execute_opus_tool(tool_name: str, tool_input: dict[str, Any]) -> str:
    if tool_name == "create_schema":
        mcp_result = call_mcp_tool("create_schema", tool_input)
        return json.dumps(mcp_result, indent=2, default=str) if mcp_result else "No data returned"

    return f"Unknown tool: {tool_name}"


class SchemaCreationSubAgent(SubAgent):
    """Sub-agent for schema creation with full structure building."""

    def __init__(self) -> None:
        config = SubAgentConfig(
            tool_name="create_schema",
            system_prompt=_SCHEMA_CREATION_SYSTEM_PROMPT,
            tools=_OPUS_TOOLS,
            max_iterations=3,
            max_tokens=8192,
        )
        super().__init__(config)

    def execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """Execute a tool call from the LLM."""
        return _execute_opus_tool(tool_name, tool_input)

    def process_response_block(self, block: Any, iteration: int, max_iterations: int) -> dict[str, Any] | None:
        """No special block processing needed for schema creation."""
        return None


def _call_opus_for_creation(name: str, requirements: str) -> SubAgentResult:
    """Call Opus model for schema creation.

    Returns:
        SubAgentResult with analysis text and token counts.
    """
    user_content = f"""Create a new schema named "{name}" with the following requirements:

{requirements}

Build the complete content array with sections, datapoints, multivalues, and tuples as needed.
Call create_schema with the full structure, then return a summary of what was created."""

    sub_agent = SchemaCreationSubAgent()
    return sub_agent.run(user_content)


@beta_tool
def create_schema_with_subagent(name: str, requirements: str) -> str:
    """Create a new Rossum schema using an Opus sub-agent.

    Delegates schema creation to a sub-agent that:
    1. Analyzes user requirements
    2. Builds complete content structure (sections, datapoints, multivalues, tuples)
    3. Creates schema via API

    Args:
        name: Name for the new schema.
        requirements: Natural language description of schema requirements.
            Describe the sections needed, field types, whether tables are required,
            and any specific extraction hints (rir_field_names).

    Returns:
        JSON with creation results including schema ID and structure summary.
    """
    start_time = time.perf_counter()

    if not name:
        return json.dumps(
            {"error": "No schema name provided", "elapsed_ms": round((time.perf_counter() - start_time) * 1000, 3)}
        )

    if not requirements:
        return json.dumps(
            {"error": "No requirements provided", "elapsed_ms": round((time.perf_counter() - start_time) * 1000, 3)}
        )

    logger.info(f"create_schema: Calling Opus for name={name}")
    result = _call_opus_for_creation(name, requirements)
    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 3)

    logger.info(
        f"create_schema: completed in {elapsed_ms:.1f}ms, "
        f"tokens in={result.input_tokens} out={result.output_tokens}, "
        f"iterations={result.iterations_used}"
    )

    return json.dumps(
        {
            "name": name,
            "analysis": result.analysis,
            "elapsed_ms": elapsed_ms,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
        },
        ensure_ascii=False,
        default=str,
    )
