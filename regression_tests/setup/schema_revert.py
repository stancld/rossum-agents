"""Setup for the schema revert regression test."""

from __future__ import annotations

import json
from pathlib import Path

from rossum_api import SyncRossumAPIClient
from rossum_api.dtos import Token

_SCHEMA_JSON = Path(__file__).resolve().parent.parent / "data" / "schema.json"
_WORKSPACE_ID = 785638


def create_queue_with_schema(api_base_url: str, api_token: str) -> dict[str, str]:
    """Create a queue with schema content from schema.json.

    Returns placeholder dict for prompt formatting: {schema_id, queue_id}.
    """
    client = SyncRossumAPIClient(base_url=api_base_url, credentials=Token(api_token))
    content = json.loads(_SCHEMA_JSON.read_text())

    schema = client.create_new_schema({"name": "Regression: Schema Revert Type Safety", "content": content})
    queue = client.create_new_queue(
        {
            "name": "Regression: Schema Revert Type Safety Queue",
            "workspace": f"{api_base_url}/workspaces/{_WORKSPACE_ID}",
            "schema": f"{api_base_url}/schemas/{schema.id}",
            "locale": "en_GB",
        }
    )

    return {"schema_id": str(schema.id), "queue_id": str(queue.id)}
