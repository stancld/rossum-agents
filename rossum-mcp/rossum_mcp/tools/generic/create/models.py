"""Pydantic create models for the unified create layer.

Each entity type has specific fields validated server-side via Pydantic.
The LLM receives a lightweight `create(entity, data: dict)` signature;
full schemas are available on-demand via `get_create_schema(entity)`.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel
from rossum_api.models.engine import EngineFieldType
from rossum_api.models.hook import HookEventAndAction, HookType
from rossum_api.models.rule import RuleAction

from rossum_mcp.tools.email_templates import EmailTemplateType
from rossum_mcp.tools.queues import QueueTemplateName


class CreateWorkspace(BaseModel):
    entity: Literal["workspace"] = "workspace"
    name: str
    organization_id: int
    metadata: dict | None = None


class CreateQueueFromTemplate(BaseModel):
    entity: Literal["queue_from_template"] = "queue_from_template"
    name: str
    template_name: QueueTemplateName
    workspace_id: int
    include_documents: bool = False
    engine_id: int | None = None


class CreateSchema(BaseModel):
    entity: Literal["schema"] = "schema"
    name: str
    content: list[dict[str, Any]]


class CreateUser(BaseModel):
    entity: Literal["user"] = "user"
    username: str
    email: str
    queues: list[str] | None = None
    groups: list[str] | None = None
    first_name: str | None = None
    last_name: str | None = None
    is_active: bool = True
    metadata: dict | None = None
    oidc_id: str | None = None
    auth_type: str = "password"


class CreateHook(BaseModel):
    entity: Literal["hook"] = "hook"
    name: str
    type: HookType
    queues: list[str] | None = None
    events: list[HookEventAndAction] | None = None
    config: dict | None = None
    settings: dict | None = None
    secret: str | None = None


class CreateHookFromTemplate(BaseModel):
    entity: Literal["hook_from_template"] = "hook_from_template"
    name: str
    hook_template_id: int
    queues: list[str]
    events: list[HookEventAndAction] | None = None
    token_owner: str | None = None


class CreateEngine(BaseModel):
    entity: Literal["engine"] = "engine"
    name: str
    organization_id: int
    engine_type: Literal["extractor", "splitter"]


class CreateEngineField(BaseModel):
    entity: Literal["engine_field"] = "engine_field"
    engine_id: int
    name: str
    label: str
    field_type: EngineFieldType
    schema_ids: list[int]
    tabular: bool = False
    multiline: bool = False
    subtype: str | None = None
    pre_trained_field_id: str | None = None


class CreateRule(BaseModel):
    entity: Literal["rule"] = "rule"
    name: str
    trigger_condition: str
    actions: list[RuleAction]
    enabled: bool = True
    schema_id: int | None = None
    queue_ids: list[int] | None = None


class CreateEmailTemplate(BaseModel):
    entity: Literal["email_template"] = "email_template"
    name: str
    queue: int
    subject: str
    message: str
    type: EmailTemplateType = "custom"
    automate: bool = False
    to: list[dict[str, Any]] | None = None
    cc: list[dict[str, Any]] | None = None
    bcc: list[dict[str, Any]] | None = None
    triggers: list[str] | None = None


CREATE_MODELS: dict[str, type[BaseModel]] = {
    "workspace": CreateWorkspace,
    "queue_from_template": CreateQueueFromTemplate,
    "schema": CreateSchema,
    "user": CreateUser,
    "hook": CreateHook,
    "hook_from_template": CreateHookFromTemplate,
    "engine": CreateEngine,
    "engine_field": CreateEngineField,
    "rule": CreateRule,
    "email_template": CreateEmailTemplate,
}

ENTITY_NOTES: dict[str, str] = {
    "queue_from_template": "Creates schema+engine as side effects.",
    "schema": "content must have at least one section with datapoints.",
    "hook": "For function hooks: config.source auto-renamed to config.code, default runtime python3.12, timeout_s capped at 60.",
    "hook_from_template": "events may override template defaults.",
    "engine": "Create matching engine_fields immediately after.",
    "engine_field": "schema_ids cannot be empty.",
    "rule": "Scope with schema_id and/or queue_ids (at least one required).",
    "email_template": "Set automate=true for automatic sending.",
}
