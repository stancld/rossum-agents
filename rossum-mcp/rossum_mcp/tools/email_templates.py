from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Literal

from rossum_api.domain_logic.resources import Resource
from rossum_api.models.email_template import EmailTemplate

from rossum_mcp.tools.base import build_filters, graceful_list, is_read_write_mode

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)

EmailTemplateType = Literal["rejection", "rejection_default", "email_with_no_processable_attachments", "custom"]


async def _get_email_template(client: AsyncRossumAPIClient, email_template_id: int) -> EmailTemplate:
    email_template: EmailTemplate = await client.retrieve_email_template(email_template_id)
    return email_template


async def _list_email_templates(
    client: AsyncRossumAPIClient,
    queue_id: int | None = None,
    type: EmailTemplateType | None = None,
    name: str | None = None,
    first_n: int | None = None,
) -> list[EmailTemplate]:
    filters = build_filters(queue=queue_id, type=type, name=name)
    result = await graceful_list(client, Resource.EmailTemplate, "email_template", max_items=first_n, **filters)
    return result.items


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
    if not is_read_write_mode():
        return {"error": "create_email_template is not available in read-only mode"}

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
    @mcp.tool(description="Retrieve one email template by ID.")
    async def get_email_template(email_template_id: int) -> EmailTemplate:
        return await _get_email_template(client, email_template_id)

    @mcp.tool(
        description="List email templates (filterable). Types: rejection, rejection_default, email_with_no_processable_attachments, custom."
    )
    async def list_email_templates(
        queue_id: int | None = None,
        type: EmailTemplateType | None = None,
        name: str | None = None,
        first_n: int | None = None,
    ) -> list[EmailTemplate]:
        return await _list_email_templates(client, queue_id, type, name, first_n)

    @mcp.tool(
        description="Create an email template; set automate=true for automatic sending. to/cc/bcc are recipient objects {type: annotator|constant|datapoint, value: ...}."
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
