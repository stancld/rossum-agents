"""Formula field suggestion tool for the Rossum Agent.

This module provides a tool to get formula suggestions from Rossum's internal API
for formula fields based on natural language descriptions.
"""

from __future__ import annotations

import json
import logging
import re

import httpx
from anthropic import beta_tool

from rossum_agent.tools.copilot._shared import _fetch_schema_content, _inject_field_into_schema, _json_headers
from rossum_agent.tools.core import get_context

logger = logging.getLogger(__name__)

_SUGGEST_FORMULA_TIMEOUT = 60


def _build_suggest_formula_url(api_base_url: str) -> str:
    """Build the suggest_formula endpoint URL.

    Uses the base URL directly (e.g., https://elis.rossum.ai/api/v1)
    and appends the internal endpoint path.
    """
    return f"{api_base_url.rstrip('/')}/internal/schemas/suggest_formula"


def _create_formula_field_definition(label: str, field_schema_id: str | None = None) -> dict:
    """Create a properly structured formula field definition."""
    if not field_schema_id:
        field_schema_id = label.lower().replace(" ", "_")
    return {
        "id": field_schema_id,
        "label": label,
        "type": "string",
        "category": "datapoint",
        "can_export": True,
        "constraints": {"required": False},
        "disable_prediction": False,
        "formula": "",
        "hidden": False,
        "rir_field_names": [],
        "score_threshold": 0,
        "suggest": True,
        "ui_configuration": {"type": "formula", "edit": "disabled"},
    }


@beta_tool
def suggest_formula_field(
    label: str, hint: str, schema_id: int, section_id: str, field_schema_id: str | None = None
) -> str:
    """Get AI-generated formula suggestions for a new formula field.

    Args:
        label: Display label for the field (e.g., 'Net Terms').
        hint: Natural language description of the formula logic.
        schema_id: The numeric schema ID (e.g., 9389721). Get this from get_schema or list_queues.
        section_id: Section ID where the field belongs. Ask the user if not specified.
        field_schema_id: Optional ID for the formula field. Defaults to label.lower().replace(" ", "_").

    Returns:
        JSON with formula suggestion and field_definition for use with patch_schema.
    """
    field_schema_id = field_schema_id or label.lower().replace(" ", "_")
    logger.info(f"suggest_formula_field: {field_schema_id=}, {schema_id=}, {section_id=}, hint={hint[:100]}...")

    try:
        api_base_url, token = get_context().require_rossum_credentials()
        url = _build_suggest_formula_url(api_base_url)

        schema_content = _fetch_schema_content(api_base_url, token, schema_id)
        field_def = _create_formula_field_definition(label, field_schema_id)
        enriched_schema = _inject_field_into_schema(schema_content, field_def, section_id)

        payload = {"field_schema_id": field_schema_id, "hint": hint, "schema_content": enriched_schema}

        logger.debug(f"Calling suggest_formula API: {url}")
        logger.debug(f"suggest_formula payload: {json.dumps(payload, indent=2)}")

        with httpx.Client(timeout=_SUGGEST_FORMULA_TIMEOUT) as client:
            response = client.post(url, json=payload, headers=_json_headers(token))
            response.raise_for_status()
            result = response.json()

        suggestions = result.get("results", [])
        if not suggestions:
            return json.dumps(
                {"status": "no_suggestions", "message": "No formula suggestions returned. Try rephrasing the hint."}
            )

        top_suggestion = suggestions[0]
        formula = top_suggestion.get("formula", "")
        summary = top_suggestion.get("summary", "")
        if summary:
            summary = _clean_html(summary)

        field_definition = _create_formula_field_definition(label, field_schema_id)
        field_definition["formula"] = formula

        return json.dumps(
            {
                "status": "success",
                "formula": formula,
                "field_definition": field_definition,
                "section_id": section_id,
                "summary": summary,
                "description": _clean_html(top_suggestion.get("description", "")),
            }
        )

    except httpx.HTTPStatusError as e:
        logger.exception("HTTP error in suggest_formula_field")
        return json.dumps(
            {
                "status": "error",
                "error": f"HTTP {e.response.status_code}: {e.response.text[:500]}",
            }
        )
    except Exception as e:
        logger.exception("Error in suggest_formula_field")
        return json.dumps({"status": "error", "error": str(e)})


def _clean_html(text: str) -> str:
    """Remove HTML tags from text (simple cleanup for display)."""
    return re.sub(r"<[^>]+>", "", text)
