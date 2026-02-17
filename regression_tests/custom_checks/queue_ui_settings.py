"""Check that queue UI settings have correct column configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from regression_tests.custom_checks._utils import create_api_client, extract_id_from_final_answer

if TYPE_CHECKING:
    from rossum_agent.agent.models import AgentStep

# Expected visible columns: (column_type, identifier)
# Based on ORGANIZATION_SETUP.md UI settings (minus "The Net Terms"):
# - status, original file name, details, Document ID, Due Date, Total Amount, Vendor Name, Received at
EXPECTED_VISIBLE_COLUMNS = {
    ("meta", "status"),
    ("meta", "original_file_name"),
    ("meta", "details"),
    ("schema", "document_id"),
    ("schema", "date_due"),
    ("schema", "sender_name"),
    ("meta", "created_at"),  # "Received at"
}

# For "Total Amount", accept any of these field IDs (varies by template)
AMOUNT_FIELD_ALTERNATIVES = {("schema", "amount_total"), ("schema", "amount_due")}


def check_queue_ui_settings(steps: list[AgentStep], api_base_url: str, api_token: str) -> tuple[bool, str]:
    """Verify that queue has correct UI column settings."""
    queue_id = extract_id_from_final_answer(steps)
    if not queue_id:
        return False, "No queue_id found in final answer"

    client = create_api_client(api_base_url, api_token)

    try:
        queue = client.retrieve_queue(int(queue_id))
    except Exception as e:
        return False, f"Failed to retrieve queue {queue_id}: {e}"

    settings = queue.settings or {}
    annotation_list_table = settings.get("annotation_list_table", {})
    columns = annotation_list_table.get("columns", [])

    if not columns:
        return False, "No columns found in queue.settings.annotation_list_table"

    # Extract actual visible columns
    actual_visible = set()
    for col in columns:
        if col.get("visible"):
            col_type = col.get("column_type")
            if col_type == "meta":
                actual_visible.add(("meta", col.get("meta_name")))
            elif col_type == "schema":
                actual_visible.add(("schema", col.get("schema_id")))

    # Check all expected columns are visible
    missing = EXPECTED_VISIBLE_COLUMNS - actual_visible
    if missing:
        missing_str = ", ".join(f"{t}:{n}" for t, n in sorted(missing))
        return False, f"Missing visible columns: {missing_str}"

    # Check that at least one amount field alternative is visible
    if not (AMOUNT_FIELD_ALTERNATIVES & actual_visible):
        alts_str = ", ".join(f"{t}:{n}" for t, n in sorted(AMOUNT_FIELD_ALTERNATIVES))
        return False, f"Missing amount field (need one of: {alts_str})"

    return True, f"All {len(EXPECTED_VISIBLE_COLUMNS) + 1} expected UI columns are visible"
