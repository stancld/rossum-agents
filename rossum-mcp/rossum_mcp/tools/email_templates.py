from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any, Literal

from rossum_api.domain_logic.resources import Resource
from rossum_api.models.email_template import EmailTemplate

from rossum_mcp.tools.base import build_filters, graceful_list

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)

EmailTemplateType = Literal["rejection", "rejection_default", "email_with_no_processable_attachments", "custom"]


async def _get_email_template(client: AsyncRossumAPIClient, email_template_id: int) -> EmailTemplate:
    return await client.retrieve_email_template(email_template_id)


async def _list_email_templates(
    client: AsyncRossumAPIClient,
    queue_id: int | None = None,
    type: EmailTemplateType | None = None,
    name: str | None = None,
    first_n: int | None = None,
    use_regex: bool = False,
) -> list[EmailTemplate]:
    logger.info(f"Listing email templates: queue_id={queue_id}, type={type}, name={name}, first_n={first_n}")
    filters = build_filters(queue=queue_id, type=type, name=None if use_regex else name)
    result = await graceful_list(client, Resource.EmailTemplate, "email_template", max_items=first_n, **filters)
    items = result.items
    if use_regex and name is not None:
        items = [t for t in items if re.search(name, t.name, re.IGNORECASE)]
    return items


async def _create_email_template(
    client: AsyncRossumAPIClient,
    name: str,
    queue: str,
    subject: str,
    message: str,
    type: EmailTemplateType = "custom",
    automate: bool = False,
    to: list[dict[str, Any]] | None = None,
    cc: list[dict[str, Any]] | None = None,
    bcc: list[dict[str, Any]] | None = None,
    triggers: list[str] | None = None,
) -> EmailTemplate | dict:
    logger.debug(f"Creating email template: name={name}, queue={queue}, type={type}")

    template_data: dict[str, Any] = {
        "name": name,
        "queue": queue,
        "subject": subject,
        "message": message,
        "type": type,
        "automate": automate,
    }

    if to is not None:
        template_data["to"] = to
    if cc is not None:
        template_data["cc"] = cc
    if bcc is not None:
        template_data["bcc"] = bcc
    if triggers is not None:
        template_data["triggers"] = triggers

    email_template: EmailTemplate = await client.create_new_email_template(template_data)
    return email_template


def register_email_template_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    @mcp.tool(
        description="Retrieve one email template by ID.",
        tags={"email_templates"},
        annotations={"readOnlyHint": True},
    )
    async def get_email_template(email_template_id: int) -> EmailTemplate:
        return await _get_email_template(client, email_template_id)

    @mcp.tool(
        description="List email templates (filterable). Types: rejection, rejection_default, email_with_no_processable_attachments, custom. Set use_regex=True to filter name as a regex pattern (client-side); otherwise name is an exact API-side match.",
        tags={"email_templates"},
        annotations={"readOnlyHint": True},
    )
    async def list_email_templates(
        queue_id: int | None = None,
        type: EmailTemplateType | None = None,
        name: str | None = None,
        first_n: int | None = None,
        use_regex: bool = False,
    ) -> list[EmailTemplate]:
        return await _list_email_templates(client, queue_id, type, name, first_n, use_regex)

    @mcp.tool(
        description="Create an email template; set automate=true for automatic sending. to/cc/bcc are recipient objects {type: annotator|constant|datapoint, value: ...}.",
        tags={"email_templates", "write"},
        annotations={"readOnlyHint": False},
    )
    async def create_email_template(
        name: str,
        queue: str,
        subject: str,
        message: str,
        type: EmailTemplateType = "custom",
        automate: bool = False,
        to: list[dict[str, Any]] | None = None,
        cc: list[dict[str, Any]] | None = None,
        bcc: list[dict[str, Any]] | None = None,
        triggers: list[str] | None = None,
    ) -> EmailTemplate | dict:
        return await _create_email_template(
            client, name, queue, subject, message, type, automate, to, cc, bcc, triggers
        )
