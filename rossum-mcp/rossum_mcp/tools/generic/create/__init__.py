"""Unified create layer: single `create` tool replacing individual create_X tools.

The LLM receives a lightweight `create(entity, data: dict)` signature.
Full schemas are available on-demand via `get_create_schema(entity)`.
Server-side Pydantic validation is preserved; validation errors include the
expected schema for self-correction.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Literal, get_args

from pydantic import ValidationError

from rossum_mcp.tools.generic.create.models import CREATE_MODELS, ENTITY_NOTES
from rossum_mcp.tools.generic.create.registry import build_create_registry

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient

CreateEntityType = Literal[
    "workspace",
    "queue_from_template",
    "schema",
    "user",
    "hook",
    "hook_from_template",
    "engine",
    "engine_field",
    "rule",
    "email_template",
]


def _serialize(obj: object) -> object:
    """Convert dataclass instances to dicts for JSON serialization."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    return obj


def _entity_schema(entity: str) -> dict:
    """Return JSON Schema for a single entity, stripping the `entity` field."""
    model = CREATE_MODELS[entity]
    schema = model.model_json_schema()
    schema.pop("title", None)
    if "properties" in schema:
        schema["properties"].pop("entity", None)
    if "required" in schema:
        schema["required"] = [f for f in schema["required"] if f != "entity"]
    return schema


def register_create_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    registry = build_create_registry(client)

    # Fail fast at startup if CreateEntityType drifts from the registry
    for _entity in get_args(CreateEntityType):
        if _entity not in registry:
            raise RuntimeError(
                f"CreateEntityType member '{_entity}' is missing from registry — "
                "update CreateEntityType or build_create_registry to keep them in sync"
            )

    @mcp.tool(
        description=("Create an entity. Call get_create_schema(entity) first to see required fields."),
        tags={"write"},
        annotations={"readOnlyHint": False},
    )
    async def create(entity: CreateEntityType, data: dict) -> object:
        model_cls = CREATE_MODELS.get(entity)
        if model_cls is None:
            return {"error": f"Unknown entity type: {entity}"}

        try:
            validated = model_cls.model_validate({"entity": entity, **data})
        except ValidationError as exc:
            return {
                "error": "Validation failed",
                "details": exc.errors(),
                "expected_schema": _entity_schema(entity),
            }

        create_fn = registry[entity]
        kwargs = validated.model_dump(exclude={"entity"})
        result = await create_fn(**kwargs)
        return _serialize(result)

    @mcp.tool(
        description="Return the JSON Schema for a specific create entity type, including notes.",
    )
    async def get_create_schema(entity: CreateEntityType) -> dict:
        if entity not in CREATE_MODELS:
            return {"error": f"Unknown entity type: {entity}"}
        schema = _entity_schema(entity)
        note = ENTITY_NOTES.get(entity)
        if note:
            schema["note"] = note
        return schema
