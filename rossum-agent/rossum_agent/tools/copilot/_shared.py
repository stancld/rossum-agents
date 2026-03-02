"""Shared helpers for copilot tools (formula, lookup, rule)."""

from __future__ import annotations

import copy
import logging

import httpx

logger = logging.getLogger(__name__)


def _json_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _fetch_schema_content(api_base_url: str, token: str, schema_id: int) -> list[dict]:
    """Fetch schema content from Rossum API."""
    url = f"{api_base_url.rstrip('/')}/schemas/{schema_id}"
    with httpx.Client(timeout=30) as client:
        response = client.get(url, headers={"Authorization": f"Bearer {token}"})
        response.raise_for_status()
        return response.json()["content"]


def _find_field_in_schema(nodes: list[dict], field_id: str) -> bool:
    """Recursively search for a field ID in schema content."""
    for node in nodes:
        if node.get("id") == field_id:
            return True
        if "children" in node:
            children = node["children"]
            if isinstance(children, list) and _find_field_in_schema(children, field_id):
                return True
            if isinstance(children, dict) and _find_field_in_schema([children], field_id):
                return True
    return False


def _inject_field_into_schema(schema_content: list[dict], field_def: dict, section_id: str) -> list[dict]:
    """Inject a field definition into the specified section of schema_content.

    The suggest_formula / suggest_computed_field APIs require the target field
    to exist in schema_content. Callers build the field_def via their own
    ``_create_*_field_definition`` helper and pass it here.
    """
    field_id = field_def.get("id")
    if not field_id or _find_field_in_schema(schema_content, field_id):
        return schema_content

    modified = copy.deepcopy(schema_content)

    for section in modified:
        if section.get("id") == section_id and section.get("category") == "section":
            section.setdefault("children", []).append(field_def)
            return modified

    if modified and modified[0].get("category") == "section":
        modified[0].setdefault("children", []).append(field_def)
    else:
        modified.append(field_def)

    return modified
