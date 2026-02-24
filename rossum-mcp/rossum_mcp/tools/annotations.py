from __future__ import annotations

import logging
from collections.abc import Sequence  # noqa: TC003 - needed at runtime for FastMCP
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import anyio
from rossum_api.domain_logic.resources import Resource
from rossum_api.models.annotation import Annotation

from rossum_mcp.tools.base import build_filters, build_resource_url, delete_resource, graceful_list

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)

type Sideload = Literal["content", "document", "automation_blocker"]


async def _upload_document(client: AsyncRossumAPIClient, file_path: str, queue_id: int) -> dict:
    path = Path(file_path)
    if not await anyio.Path(path).exists():
        logger.error(f"File not found: {file_path}")
        raise FileNotFoundError(f"File not found: {file_path}")

    try:
        task = (await client.upload_document(queue_id, [(str(path), path.name)]))[0]
    except KeyError as e:
        logger.error(f"Upload failed - unexpected API response format: {e!s}")
        error_msg = (
            f"Document upload failed - API response missing expected key {e!s}. "
            f"This usually means either:\n"
            f"1. The queue_id ({queue_id}) is invalid or you don't have access to it\n"
            f"2. The Rossum API returned an error response\n"
            f"Please verify:\n"
            f"- The queue_id is correct and exists in your workspace\n"
            f"- You have permission to upload documents to this queue\n"
            f"- Your API token has the necessary permissions"
        )
        raise ValueError(error_msg) from e
    except IndexError as e:
        logger.error(f"Upload failed - no tasks returned: {e}")
        raise ValueError(
            f"Document upload failed - no tasks were created. This may indicate the queue_id ({queue_id}) is invalid."
        ) from e
    except Exception as e:
        logger.error(f"Upload failed: {type(e).__name__}: {e}")
        raise ValueError(f"Document upload failed: {type(e).__name__}: {e!s}") from e

    return {
        "task_id": task.id,
        "task_status": task.status,
        "queue_id": queue_id,
        "message": "Document upload initiated. Use `list_annotations` to find the annotation ID for this queue.",
    }


async def _get_annotation(
    client: AsyncRossumAPIClient, annotation_id: int, sideloads: Sequence[Sideload] = ()
) -> Annotation:
    logger.debug(f"Retrieving annotation: annotation_id={annotation_id}")
    annotation: Annotation = await client.retrieve_annotation(annotation_id, sideloads)  # type: ignore[arg-type]
    return annotation


async def _list_annotations(
    client: AsyncRossumAPIClient,
    queue_id: int,
    status: str | None = "importing,to_review,confirmed,exported",
    ordering: Sequence[str] = (),
    first_n: int | None = None,
) -> list[Annotation]:
    logger.debug(f"Listing annotations: queue_id={queue_id}, status={status}, ordering={ordering}, first_n={first_n}")
    filters = build_filters(queue=queue_id, page_size=100, status=status, ordering=ordering or None)
    result = await graceful_list(client, Resource.Annotation, "annotation", max_items=first_n, **filters)
    return result.items


async def _start_annotation(client: AsyncRossumAPIClient, annotation_id: int) -> dict:
    logger.debug(f"Starting annotation: annotation_id={annotation_id}")
    await client.start_annotation(annotation_id)
    return {
        "annotation_id": annotation_id,
        "message": f"Annotation {annotation_id} started successfully. Status changed to 'reviewing'.",
    }


async def _bulk_update_annotation_fields(
    client: AsyncRossumAPIClient, annotation_id: int, operations: list[dict]
) -> dict:
    logger.debug(f"Bulk updating annotation: annotation_id={annotation_id}, ops={operations}")
    await client.bulk_update_annotation_data(annotation_id, operations)
    return {
        "annotation_id": annotation_id,
        "operations_count": len(operations),
        "message": f"Annotation {annotation_id} updated with {len(operations)} operations successfully.",
    }


async def _confirm_annotation(client: AsyncRossumAPIClient, annotation_id: int) -> dict:
    logger.debug(f"Confirming annotation: annotation_id={annotation_id}")
    await client.confirm_annotation(annotation_id)
    return {
        "annotation_id": annotation_id,
        "message": f"Annotation {annotation_id} confirmed successfully. Status changed to 'confirmed'.",
    }


async def _copy_annotations(
    client: AsyncRossumAPIClient,
    annotation_ids: Sequence[int],
    target_queue_id: int,
    target_status: str | None = None,
    reimport: bool = False,
) -> dict:
    target_queue_url = build_resource_url("queues", target_queue_id)
    params = {"reimport": "true"} if reimport else {}

    results: list[dict] = []
    errors: list[dict] = []
    for annotation_id in annotation_ids:
        try:
            payload: dict = {"target_queue": target_queue_url}
            if target_status is not None:
                payload["target_status"] = target_status

            response = await client._http_client.request_json(
                method="POST",
                url=f"annotations/{annotation_id}/copy",
                json=payload,
                params=params,
            )
            results.append({"annotation_id": annotation_id, "copied_annotation": response})
        except Exception as e:
            errors.append({"annotation_id": annotation_id, "error": f"{type(e).__name__}: {e!s}"})

    return {"copied": len(results), "failed": len(errors), "results": results, "errors": errors}


async def _delete_annotation(client: AsyncRossumAPIClient, annotation_id: int) -> dict:
    return await delete_resource(
        "annotation", annotation_id, client.delete_annotation, f"Annotation {annotation_id} moved to 'deleted' status"
    )


def register_annotation_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    @mcp.tool(
        description="Upload a document; use list_annotations to find the created annotation.",
        tags={"annotations", "write"},
        annotations={"readOnlyHint": False},
    )
    async def upload_document(file_path: str, queue_id: int) -> dict:
        return await _upload_document(client, file_path, queue_id)

    @mcp.tool(
        description="Retrieve an annotation; include sideload='content' to return extracted data.",
        tags={"annotations"},
        annotations={"readOnlyHint": True},
    )
    async def get_annotation(annotation_id: int, sideloads: Sequence[Sideload] = ()) -> Annotation:
        return await _get_annotation(client, annotation_id, sideloads)

    @mcp.tool(
        description="List queue annotations; ordering=['-created_at'] returns newest first.",
        tags={"annotations"},
        annotations={"readOnlyHint": True},
    )
    async def list_annotations(
        queue_id: int,
        status: str | None = "importing,to_review,confirmed,exported",
        ordering: Sequence[str] = (),
        first_n: int | None = None,
    ) -> list[Annotation]:
        return await _list_annotations(client, queue_id, status, ordering, first_n)

    @mcp.tool(
        description="Set annotation status to 'reviewing' (from 'to_review').",
        tags={"annotations", "write"},
        annotations={"readOnlyHint": False},
    )
    async def start_annotation(annotation_id: int) -> dict:
        return await _start_annotation(client, annotation_id)

    @mcp.tool(
        description="Bulk update extracted fields. Requires annotation in 'reviewing' status. Use datapoint IDs from content, not schema_id.",
        tags={"annotations", "write"},
        annotations={"readOnlyHint": False},
    )
    async def bulk_update_annotation_fields(annotation_id: int, operations: list[dict]) -> dict:
        return await _bulk_update_annotation_fields(client, annotation_id, operations)

    @mcp.tool(
        description="Set annotation status to 'confirmed' (typically after field updates).",
        tags={"annotations", "write"},
        annotations={"readOnlyHint": False},
    )
    async def confirm_annotation(annotation_id: int) -> dict:
        return await _confirm_annotation(client, annotation_id)

    @mcp.tool(
        description="Copy annotations to another queue. reimport=True re-extracts data in the target queue (use when moving/uploading documents between queues). reimport=False preserves original extracted data as-is.",
        tags={"annotations", "write"},
        annotations={"readOnlyHint": False},
    )
    async def copy_annotations(
        annotation_ids: Sequence[int],
        target_queue_id: int,
        target_status: str | None = None,
        reimport: bool = False,
    ) -> dict:
        return await _copy_annotations(client, annotation_ids, target_queue_id, target_status, reimport)

    @mcp.tool(
        description="Soft-delete an annotation (status 'deleted').",
        tags={"annotations", "write"},
        annotations={"readOnlyHint": False, "destructiveHint": True},
    )
    async def delete_annotation(annotation_id: int) -> dict:
        return await _delete_annotation(client, annotation_id)
