"""Message endpoints with SSE streaming."""

from __future__ import annotations

import asyncio
import contextlib
import contextvars
import logging
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from rossum_agent.agent.memory import AgentMemory
from rossum_agent.api.dependencies import (
    RossumCredentials,
    get_agent_service,
    get_chat_service,
    get_validated_credentials,
)
from rossum_agent.api.models.schemas import (
    CancelResponse,
    DocumentContent,
    FileCreatedEvent,
    ImageContent,
    MessageRequest,
    StepEvent,
    StreamDoneEvent,
    SubAgentProgressEvent,
    SubAgentTextEvent,
    TaskSnapshotEvent,
)
from rossum_agent.api.services.agent_service import AgentService
from rossum_agent.api.services.chat_service import ChatService
from rossum_agent.redis_storage import ChatData

# To prevent (legacy) proxy servers from dropping connections during long periods of thinking,
# we are sending SSE_KEEPALIVE_COMMENT every SSE_KEEPALIVE_INTERVAL as per recommendation:
# https://html.spec.whatwg.org/multipage/server-sent-events.html#authoring-notes
SSE_KEEPALIVE_INTERVAL = 15
SSE_KEEPALIVE_COMMENT = ": keepalive\n\n"

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/chats", tags=["messages"])


def _format_sse_event(event_type: str, data: str) -> str:
    """Format an SSE event string."""
    return f"event: {event_type}\ndata: {data}\n\n"


type AgentEvent = StreamDoneEvent | SubAgentProgressEvent | SubAgentTextEvent | TaskSnapshotEvent | StepEvent


@dataclass
class ProcessedEvent:
    """Result of processing an agent event."""

    sse_event: str | None = None
    done_event: StreamDoneEvent | None = None
    final_response_update: str | None = None


def _process_agent_event(event: AgentEvent) -> ProcessedEvent:
    """Process a single agent event and return structured result."""
    if isinstance(event, StreamDoneEvent):
        return ProcessedEvent(done_event=event)
    if isinstance(event, SubAgentProgressEvent):
        return ProcessedEvent(sse_event=_format_sse_event("sub_agent_progress", event.model_dump_json()))
    if isinstance(event, SubAgentTextEvent):
        return ProcessedEvent(sse_event=_format_sse_event("sub_agent_text", event.model_dump_json()))
    if isinstance(event, TaskSnapshotEvent):
        return ProcessedEvent(sse_event=_format_sse_event("task_snapshot", event.model_dump_json()))
    sse = _format_sse_event("step", event.model_dump_json())
    if event.type == "final_answer" and event.is_streaming:
        return ProcessedEvent(sse_event=sse, final_response_update=event.content)
    final_response = event.content if event.type == "final_answer" and event.content else None
    return ProcessedEvent(sse_event=sse, final_response_update=final_response)


def _yield_file_events(output_dir: Path | None, chat_id: str) -> Iterator[str]:
    """Yield SSE events for created files in the output directory."""
    if output_dir is None or not output_dir.exists():
        return
    for file_path in output_dir.iterdir():
        if file_path.is_file():
            file_event = FileCreatedEvent(
                filename=file_path.name, url=f"/api/v1/chats/{chat_id}/files/{file_path.name}"
            )
            yield _format_sse_event("file_created", file_event.model_dump_json())


def _save_chat_history(
    chat_service: ChatService,
    agent_service: AgentService,
    credentials: RossumCredentials,
    chat_id: str,
    chat_data: ChatData,
    history: list[dict],
    user_prompt: str,
    final_response: str | None,
    images: list[ImageContent] | None,
    documents: list[DocumentContent] | None,
    output_dir: Path | None,
    memory: AgentMemory | None,
    done_event: StreamDoneEvent | None = None,
) -> None:
    """Persist updated conversation history after a successful agent run."""
    if done_event and done_event.config_commit_hash:
        chat_data.metadata.config_commits.append(done_event.config_commit_hash)

    updated_history = agent_service.build_updated_history(
        existing_history=history,
        user_prompt=user_prompt,
        final_response=final_response,
        images=images,
        documents=documents,
        memory=memory,
    )
    chat_service.save_messages(
        user_id=credentials.user_id,
        chat_id=chat_id,
        messages=updated_history,
        output_dir=output_dir,
        metadata=chat_data.metadata,
    )


async def _watch_disconnect(request: Request, chat_id: str, agent_service: AgentService) -> None:
    """Poll for client disconnect and cancel the running agent."""
    try:
        while True:
            if await request.is_disconnected():
                logger.info(f"Client disconnected for chat {chat_id}, cancelling run")
                agent_service.cancel_run(chat_id)
                return
            await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        logger.debug(f"Disconnect watcher for chat {chat_id} cancelled")


def _resolve_mcp_mode(message: MessageRequest, chat_data: ChatData) -> str:
    """Resolve the effective MCP mode from the message and chat metadata."""
    if message.mcp_mode is not None:
        chat_data.metadata.mcp_mode = message.mcp_mode
        return message.mcp_mode
    return chat_data.metadata.mcp_mode


async def _with_sse_keepalive(
    events: AsyncIterator[AgentEvent],
    interval: float = SSE_KEEPALIVE_INTERVAL,
) -> AsyncIterator[tuple[AgentEvent | None, bool]]:
    """Wrap an async event stream with periodic SSE keepalive signals.

    Yields (event, False) for real events and (None, True) for keepalive ticks.
    This prevents reverse proxies from closing idle connections during long
    model thinking pauses.

    Uses asyncio.wait() instead of asyncio.wait_for() to avoid cancelling the
    pending anext() task on timeout, which would corrupt the async generator state.

    Context is captured from each completed task and passed to the next one,
    so that context variables set by the async generator (e.g. output_dir)
    propagate across iterations.
    """
    ctx: contextvars.Context | None = None
    pending: asyncio.Task = asyncio.create_task(anext(events))
    try:
        while True:
            done, _ = await asyncio.wait({pending}, timeout=interval)
            if not done:
                yield None, True
                continue
            ctx = pending.get_context()
            try:
                event = pending.result()
            except StopAsyncIteration:
                break
            yield event, False
            pending = asyncio.create_task(anext(events), context=ctx)
    finally:
        if not pending.done():
            pending.cancel()
            with contextlib.suppress(asyncio.CancelledError, StopAsyncIteration):
                await pending


@router.post(
    "/{chat_id}/messages",
    response_class=StreamingResponse,
    responses={
        200: {"description": "SSE stream of agent step events", "content": {"text/event-stream": {}}},
        404: {"description": "Chat not found"},
        429: {"description": "Rate limit exceeded"},
    },
)
@limiter.limit("10/minute")
async def send_message(
    request: Request,
    chat_id: str,
    message: MessageRequest,
    credentials: Annotated[RossumCredentials, Depends(get_validated_credentials)] = None,  # type: ignore[assignment]
    chat_service: Annotated[ChatService, Depends(get_chat_service)] = None,  # type: ignore[assignment]
    agent_service: Annotated[AgentService, Depends(get_agent_service)] = None,  # type: ignore[assignment]
) -> StreamingResponse:
    """Send a message and stream the agent's response via SSE.

    If a previous request is still running for this chat, it will be cancelled
    before starting the new one. Client disconnects are also detected and will
    cancel the running agent.
    """
    chat_data = chat_service.get_chat_data(credentials.user_id, chat_id)
    if chat_data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chat {chat_id} not found")

    history = chat_data.messages
    mcp_mode = _resolve_mcp_mode(message, chat_data)
    user_prompt = message.content
    images: list[ImageContent] | None = message.images
    documents: list[DocumentContent] | None = message.documents

    async def event_generator() -> Iterator[str]:  # type: ignore[misc]
        final_response: str | None = None
        done_event: StreamDoneEvent | None = None

        watcher = asyncio.create_task(_watch_disconnect(request, chat_id, agent_service))

        try:
            agent_events = agent_service.run_agent(
                chat_id=chat_id,
                prompt=user_prompt,
                images=images,
                documents=documents,
                conversation_history=history,
                rossum_api_token=credentials.token,
                rossum_api_base_url=credentials.api_url,
                rossum_url=message.rossum_url,
                mcp_mode=mcp_mode,
            )
            async for event, is_keepalive in _with_sse_keepalive(agent_events):
                if is_keepalive:
                    yield SSE_KEEPALIVE_COMMENT
                    continue
                result = _process_agent_event(event)
                if result.done_event:
                    done_event = result.done_event
                # Hook output is shown in chat but excluded from conversation history
                if result.final_response_update and not (isinstance(event, StepEvent) and event.is_hook_output):
                    final_response = result.final_response_update
                if result.sse_event:
                    yield result.sse_event

        except asyncio.CancelledError:
            logger.info(f"Request cancelled for chat {chat_id}")
            return

        except Exception as e:
            logger.error(f"Error during agent execution: {e}", exc_info=True)
            error_event = StepEvent(type="error", step_number=0, content=str(e), is_final=True)
            yield _format_sse_event("step", error_event.model_dump_json())
            return

        finally:
            watcher.cancel()

        output_dir = agent_service.get_output_dir(chat_id)
        memory = agent_service.pop_last_memory(chat_id)

        _save_chat_history(
            chat_service=chat_service,
            agent_service=agent_service,
            credentials=credentials,
            chat_id=chat_id,
            chat_data=chat_data,
            history=history,
            user_prompt=user_prompt,
            final_response=final_response,
            images=images,
            documents=documents,
            output_dir=output_dir,
            memory=memory,
            done_event=done_event,
        )

        for file_event in _yield_file_events(output_dir, chat_id):
            yield file_event

        if done_event:
            yield _format_sse_event("done", done_event.model_dump_json())

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.post(
    "/{chat_id}/cancel",
    response_model=CancelResponse,
    responses={
        200: {"description": "Cancellation result"},
        404: {"description": "Chat not found"},
    },
)
async def cancel_message(
    request: Request,
    chat_id: str,
    credentials: Annotated[RossumCredentials, Depends(get_validated_credentials)] = None,  # type: ignore[assignment]
    chat_service: Annotated[ChatService, Depends(get_chat_service)] = None,  # type: ignore[assignment]
    agent_service: Annotated[AgentService, Depends(get_agent_service)] = None,  # type: ignore[assignment]
) -> CancelResponse:
    """Cancel a running agent request for a chat."""
    if not chat_service.chat_exists(credentials.user_id, chat_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chat {chat_id} not found")

    cancelled = agent_service.cancel_run(chat_id)
    return CancelResponse(cancelled=cancelled)
