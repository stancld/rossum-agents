"""Category metadata for dynamic tool discovery.

Provides descriptions and keywords for tool categories. Tool membership and
read_only status are derived from tags set on individual @mcp.tool decorators.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CategoryMeta:
    """Lightweight metadata for a tool category."""

    description: str
    keywords: list[str]


# Category descriptions and keywords for agent pre-loading.
# Tool lists are derived dynamically from tags on @mcp.tool decorators.
CATEGORY_META: dict[str, CategoryMeta] = {
    "annotations": CategoryMeta(
        description="Document processing: upload, retrieve, update, and confirm annotations",
        keywords=["annotation", "document", "upload", "extract", "confirm", "review"],
    ),
    "queues": CategoryMeta(
        description="Queue management: create, configure, and list document processing queues",
        keywords=["queue", "inbox", "connector"],
    ),
    "schemas": CategoryMeta(
        description="Schema management: define and modify document field structures",
        keywords=["schema", "field", "datapoint", "section", "multivalue", "tuple"],
    ),
    "engines": CategoryMeta(
        description="AI engine management: create and configure extraction/splitting engines",
        keywords=["engine", "ai", "extractor", "splitter", "training"],
    ),
    "hooks": CategoryMeta(
        description="Extensions/webhooks: create and manage automation hooks",
        keywords=["hook", "extension", "webhook", "automation", "function", "serverless"],
    ),
    "email_templates": CategoryMeta(
        description="Email templates: configure automated email responses",
        keywords=["email", "template", "notification", "rejection"],
    ),
    "document_relations": CategoryMeta(
        description="Document relations: manage export/einvoice document links",
        keywords=["document relation", "export", "einvoice"],
    ),
    "relations": CategoryMeta(
        description="Annotation relations: manage edit/attachment/duplicate links",
        keywords=["relation", "duplicate", "attachment"],
    ),
    "rules": CategoryMeta(
        description="Validation rules: manage schema validation rules",
        keywords=["rule", "validation", "constraint"],
    ),
    "organization_groups": CategoryMeta(
        description="Organization group management: view license groups shared across organizations",
        keywords=[
            "organization group",
            "license",
            "trial",
            "production",
            "deployment",
            "lookup fields",
            "datasets",
            "reasoning fields",
        ],
    ),
    "organization_limits": CategoryMeta(
        description="Organization limits: view email sending limits and usage counters",
        keywords=["organization limit", "email limit", "quota", "email usage"],
    ),
    "users": CategoryMeta(
        description="User management: create, update, list users and roles",
        keywords=["user", "role", "permission", "token_owner"],
    ),
    "workspaces": CategoryMeta(
        description="Workspace management: organize queues into workspaces",
        keywords=["workspace", "organization"],
    ),
}


def get_catalog_summary() -> str:
    """Get a compact text summary of all tool categories for the system prompt."""
    lines = ["Available MCP tool categories (use `list_tool_categories` for details):"]
    for name, meta in CATEGORY_META.items():
        lines.append(f"- **{name}**: {meta.description}")
    return "\n".join(lines)
