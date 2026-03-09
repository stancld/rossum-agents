"""Check that schema contains a properly configured lookup field and evaluation succeeded."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from rossum_agent.agent.models import ToolResultStep

from regression_tests.custom_checks._utils import create_api_client, extract_schema_id_from_steps

if TYPE_CHECKING:
    from rossum_agent.agent.models import AgentStep

# Expected vendor matches: sender_name -> match expected (True) or not (False/None)
# McDonald's has two entries in the dataset (Hamburg + Berlin) with no VAT on the document → ambiguous, no match
# evaluate_lookup_field returns value="" when no match, non-empty value (MDH record ID) when matched
EXPECTED_VENDOR_MATCHES: dict[str, bool] = {
    "Copy General": True,
    "Microsoft": True,
    "Siemens AG": True,
    "McDonald's": False,
    "Google": True,
    "General Electric Ltd.": True,
    "Blockbuster LLC": True,
}


def _find_lookup_field_raw(schema_content: list[dict]) -> dict | None:
    """Find the first lookup field in raw schema content (preserves matching dict)."""
    for section in schema_content:
        for child in section.get("children", []):
            ui_config = child.get("ui_configuration") or {}
            if isinstance(ui_config, dict) and ui_config.get("type") == "lookup":
                return child
            # Check multivalue children too
            for grandchild in child.get("children", []):
                if not isinstance(grandchild, dict):
                    continue
                ui_config = grandchild.get("ui_configuration") or {}
                if isinstance(ui_config, dict) and ui_config.get("type") == "lookup":
                    return grandchild
    return None


def _find_evaluate_result(steps: list[AgentStep]) -> dict | None:
    """Find the last successful evaluate_lookup_field tool result."""
    for step in reversed(steps):
        if not isinstance(step, ToolResultStep):
            continue
        for tc in step.tool_calls:
            if tc.name == "evaluate_lookup_field":
                for tr in step.tool_results:
                    if tr.tool_call_id == tc.id and isinstance(tr.content, str):
                        try:
                            parsed = json.loads(tr.content)
                        except json.JSONDecodeError:
                            continue
                        if parsed.get("status") == "success":
                            return parsed
    return None


def _aggregate_lookup_results(eval_result: dict) -> list[dict]:
    """Flatten lookup_results from all per-annotation results."""
    aggregated = []
    for r in eval_result.get("results", []):
        aggregated.extend(r.get("lookup_results", []))
    return aggregated


def check_lookup_field_configured(steps: list[AgentStep], api_base_url: str, api_token: str) -> tuple[bool, str]:
    """Verify schema has a lookup field with valid matching config and evaluation succeeded."""
    schema_id = extract_schema_id_from_steps(steps)
    if not schema_id:
        return False, "Could not find schema_id in agent steps"

    # Fetch raw schema to preserve matching dict (not in Datapoint model)
    client = create_api_client(api_base_url, api_token)
    raw_schema = client.request_json("GET", f"schemas/{schema_id}")
    schema_content = raw_schema.get("content", [])

    lookup_field = _find_lookup_field_raw(schema_content)
    if not lookup_field:
        return False, f"No lookup field (ui_configuration.type == 'lookup') found in schema {schema_id}"

    # Validate matching configuration
    matching = lookup_field.get("matching")
    if not matching or not isinstance(matching, dict):
        return False, f"Lookup field has no matching configuration: {lookup_field.get('id')}"

    matching_type = matching.get("type")
    if not matching_type:
        return False, f"Lookup field matching.type is not set: {matching}"

    config = matching.get("configuration", {})
    if not config.get("dataset"):
        return False, f"Lookup field matching.configuration.dataset is not set: {config}"

    if not config.get("queries"):
        return False, f"Lookup field matching.configuration.queries is empty: {config}"

    if not config.get("placeholders") and not config.get("variables"):
        return False, f"Lookup field matching.configuration has no placeholders or variables: {config}"

    # Verify evaluate_lookup_field was called and succeeded
    eval_result = _find_evaluate_result(steps)
    if not eval_result:
        return False, "evaluate_lookup_field was not called or returned no parseable result"

    lookup_results = _aggregate_lookup_results(eval_result)
    if not lookup_results:
        return False, "evaluate_lookup_field returned empty lookup_results"

    # Verify at least one result has non-empty matching field values
    has_matching_values = any(any(v for v in r.get("matching_fields", {}).values()) for r in lookup_results)
    if not has_matching_values:
        return False, f"No lookup result has non-empty matching_fields values: {lookup_results}"

    return True, (
        f"Schema {schema_id} has lookup field '{lookup_field.get('id')}' "
        f"with matching type '{matching_type}', "
        f"dataset '{config.get('dataset')}', "
        f"{len(config.get('queries', []))} queries, "
        f"{len(config.get('placeholders', []))} placeholders. "
        f"Evaluation succeeded with {len(lookup_results)} lookup results "
        f"with matching field values."
    )


def check_lookup_match_results(steps: list[AgentStep], _api_base_url: str, _api_token: str) -> tuple[bool, str]:
    """Verify lookup match results in output.json match expected vendor matches.

    Uses value (non-empty = matched) since evaluate_lookup_field populates options=[] for unambiguous matches.
    """
    eval_result = _find_evaluate_result(steps)
    if not eval_result:
        return False, "evaluate_lookup_field was not called or returned no parseable result"

    lookup_results = _aggregate_lookup_results(eval_result)
    if not lookup_results:
        return False, "evaluate_lookup_field returned empty lookup_results"

    if len(lookup_results) != len(EXPECTED_VENDOR_MATCHES):
        return False, f"Expected {len(EXPECTED_VENDOR_MATCHES)} lookup results, got {len(lookup_results)}"

    # Build actual matches: sender_name -> whether a match was found (non-empty value)
    actual_matched: dict[str, bool] = {
        result.get("matching_fields", {}).get("sender_name", ""): bool(result.get("value", ""))
        for result in lookup_results
    }

    mismatches: list[str] = []
    for sender_name, expected_match in EXPECTED_VENDOR_MATCHES.items():
        if sender_name not in actual_matched:
            mismatches.append(f"'{sender_name}' not found in results")
            continue
        actual = actual_matched[sender_name]
        if expected_match and not actual:
            mismatches.append(f"'{sender_name}' expected a match but value was empty")
        elif not expected_match and actual:
            value = next(
                (
                    r.get("value")
                    for r in lookup_results
                    if r.get("matching_fields", {}).get("sender_name") == sender_name
                ),
                "?",
            )
            mismatches.append(f"'{sender_name}' expected no match but got value '{value}'")

    if mismatches:
        return False, f"Vendor match mismatches: {'; '.join(mismatches)}"

    matched_count = sum(1 for v in EXPECTED_VENDOR_MATCHES.values() if v)
    return True, (
        f"All {len(EXPECTED_VENDOR_MATCHES)} vendor match expectations correct: "
        f"{matched_count} matched, {len(EXPECTED_VENDOR_MATCHES) - matched_count} unmatched as expected"
    )
