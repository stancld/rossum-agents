"""Agent service for running the Rossum Agent."""

from __future__ import annotations

import asyncio
import contextlib
import contextvars
import dataclasses
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from rossum_agent.agent.core import RossumAgent, create_agent
from rossum_agent.agent.memory import AgentMemory
from rossum_agent.agent.models import AgentConfig, AgentStep, StepType, ToolResult
from rossum_agent.api.models.schemas import (
    DocumentContent,
    ImageContent,
    StepEvent,
    StreamDoneEvent,
    SubAgentProgressEvent,
    SubAgentTextEvent,
    TaskSnapshotEvent,
)
from rossum_agent.prompts import get_system_prompt
from rossum_agent.rossum_mcp_integration import connect_mcp_server
from rossum_agent.tools import (
    SubAgentProgress,
    SubAgentText,
    TaskTracker,
    set_mcp_connection,
    set_output_dir,
    set_progress_callback,
    set_rossum_credentials,
    set_task_snapshot_callback,
    set_task_tracker,
    set_text_callback,
)
from rossum_agent.url_context import extract_url_context, format_context_for_prompt
from rossum_agent.utils import create_session_output_dir, get_display_tool_name

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable
    from pathlib import Path

    from anthropic.types import ImageBlockParam, TextBlockParam

    from rossum_agent.agent.types import UserContent

logger = logging.getLogger(__name__)


@dataclass
class _RequestContext:
    """Per-request context for agent execution."""

    event_queue: asyncio.Queue[SubAgentProgressEvent | SubAgentTextEvent | TaskSnapshotEvent] | None = None
    event_loop: asyncio.AbstractEventLoop | None = None


@dataclass
class _ChatRunState:
    """Per-chat run tracking for cancellation support."""

    lock: asyncio.Lock = dataclasses.field(default_factory=asyncio.Lock)
    active_task: asyncio.Task | None = None
    run_id: int = 0
    output_dir: Path | None = None
    last_memory: AgentMemory | None = None


_request_context: contextvars.ContextVar[_RequestContext] = contextvars.ContextVar("request_context")


def convert_sub_agent_progress_to_event(progress: SubAgentProgress) -> SubAgentProgressEvent:
    """Convert a SubAgentProgress to a SubAgentProgressEvent for SSE streaming.

    Args:
        progress: The SubAgentProgress from the internal tool.

    Returns:
        SubAgentProgressEvent suitable for SSE transmission.
    """
    return SubAgentProgressEvent(
        tool_name=progress.tool_name,
        iteration=progress.iteration,
        max_iterations=progress.max_iterations,
        current_tool=progress.current_tool,
        tool_calls=progress.tool_calls,
        status=progress.status,
    )


def _create_tool_start_event(step: AgentStep, current_tool: str) -> StepEvent:
    """Create a tool_start event from an AgentStep."""
    current_tool_args = None
    current_tool_call_id = None
    for tc in step.tool_calls:
        if tc.name == current_tool:
            current_tool_args = tc.arguments
            current_tool_call_id = tc.id
            break
    display_name = get_display_tool_name(current_tool, current_tool_args)
    return StepEvent(
        type="tool_start",
        step_number=step.step_number,
        tool_name=display_name,
        tool_arguments=current_tool_args,
        tool_progress=step.tool_progress,
        tool_call_id=current_tool_call_id,
    )


def _create_tool_result_event(step_number: int, result: ToolResult) -> StepEvent:
    """Create a tool_result event from a single ToolResult."""
    return StepEvent(
        type="tool_result",
        step_number=step_number,
        tool_name=result.name,
        result=result.content,
        is_error=result.is_error,
        tool_call_id=result.tool_call_id,
    )


def _log_events(events: list[StepEvent]) -> None:
    for e in events:
        logger.info(
            f"StepEvent: type={e.type}, step={e.step_number}, "
            f"tool_call_id={e.tool_call_id}, is_streaming={e.is_streaming}"
        )


def _handle_error(step: AgentStep) -> list[StepEvent] | None:
    if not step.error:
        return None
    return [StepEvent(type="error", step_number=step.step_number, content=step.error, is_final=True)]


def _handle_final_answer(step: AgentStep) -> list[StepEvent] | None:
    if not (step.is_final and step.final_answer):
        return None
    return [StepEvent(type="final_answer", step_number=step.step_number, content=step.final_answer, is_final=True)]


def _handle_intermediate_text(step: AgentStep) -> list[StepEvent] | None:
    if not (step.step_type == StepType.INTERMEDIATE and step.accumulated_text is not None):
        return None
    return [
        StepEvent(type="intermediate", step_number=step.step_number, content=step.accumulated_text, is_streaming=True)
    ]


def _handle_streaming_final_answer(step: AgentStep) -> list[StepEvent] | None:
    if not (step.step_type == StepType.FINAL_ANSWER and step.accumulated_text is not None):
        return None
    return [
        StepEvent(type="final_answer", step_number=step.step_number, content=step.accumulated_text, is_streaming=True)
    ]


def _handle_current_tool(step: AgentStep) -> list[StepEvent] | None:
    if not (step.current_tool and step.tool_progress):
        return None
    return [_create_tool_start_event(step, step.current_tool)]


def _handle_streaming_tool_calls(step: AgentStep) -> list[StepEvent] | None:
    if not (step.tool_calls and step.is_streaming and step.tool_progress):
        return None
    total = len(step.tool_calls)
    events: list[StepEvent] = []
    for idx, tc in enumerate(step.tool_calls, 1):
        ev = _create_tool_start_event(step, tc.name)
        ev.tool_progress = (idx, total)
        events.append(ev)
    return events


def _handle_tool_results(step: AgentStep) -> list[StepEvent] | None:
    if not (step.tool_results and not step.is_streaming):
        return None
    return [_create_tool_result_event(step.step_number, r) for r in step.tool_results]


def _handle_thinking(step: AgentStep) -> list[StepEvent] | None:
    if not (step.step_type == StepType.THINKING or step.thinking is not None):
        return None
    return [
        StepEvent(type="thinking", step_number=step.step_number, content=step.thinking, is_streaming=step.is_streaming)
    ]


_STEP_HANDLERS: tuple[Callable[[AgentStep], list[StepEvent] | None], ...] = (
    _handle_error,
    _handle_final_answer,
    _handle_intermediate_text,
    _handle_streaming_final_answer,
    _handle_current_tool,
    _handle_streaming_tool_calls,
    _handle_tool_results,
    _handle_thinking,
)


def convert_step_to_events(step: AgentStep) -> list[StepEvent]:
    """Convert an AgentStep to StepEvents for SSE streaming.

    Extended thinking mode produces three distinct content types:
    - "thinking": Model's chain-of-thought reasoning (from thinking blocks)
    - "intermediate": Model's response text before tool calls
    - "final_answer": Model's final response (no more tool calls)

    Per Claude's extended thinking API, thinking blocks contain internal reasoning
    while text blocks contain the actual response. Both are streamed separately.

    Returns a list because a single step may contain multiple tool results.
    """
    for handler in _STEP_HANDLERS:
        events = handler(step)
        if events is not None:
            _log_events(events)
            return events

    events = [StepEvent(type="thinking", step_number=step.step_number, content=None, is_streaming=step.is_streaming)]
    _log_events(events)
    return events


class AgentService:
    """Service for running the Rossum Agent.

    Manages MCP connection lifecycle and agent execution for API requests.
    Uses contextvars for per-request state to support concurrent requests.
    """

    def __init__(self) -> None:
        """Initialize agent service."""
        self._chat_runs: dict[str, _ChatRunState] = {}

    def _get_context(self) -> _RequestContext:
        """Get the current request context, creating if needed."""
        try:
            return _request_context.get()
        except LookupError:
            ctx = _RequestContext()
            _request_context.set(ctx)
            return ctx

    def _get_chat_run_state(self, chat_id: str) -> _ChatRunState:
        """Get or create run state for a chat."""
        if chat_id not in self._chat_runs:
            self._chat_runs[chat_id] = _ChatRunState()
        return self._chat_runs[chat_id]

    async def _register_run(self, chat_id: str) -> int:
        """Register a new run for a chat, cancelling any existing run.

        Returns the new run_id for tracking.
        """
        state = self._get_chat_run_state(chat_id)
        async with state.lock:
            if state.active_task is not None and not state.active_task.done():
                logger.info(f"Cancelling existing run for chat {chat_id} (run_id={state.run_id})")
                state.active_task.cancel()
                with contextlib.suppress(TimeoutError, asyncio.CancelledError, Exception):
                    await asyncio.wait_for(asyncio.shield(state.active_task), timeout=2.0)
            state.run_id += 1
            state.active_task = asyncio.current_task()
            logger.info(f"Registered run_id={state.run_id} for chat {chat_id}")
            return state.run_id

    async def _clear_run(self, chat_id: str, run_id: int) -> None:
        """Clear the active run if it matches the given run_id."""
        state = self._get_chat_run_state(chat_id)
        async with state.lock:
            if state.run_id == run_id:
                state.active_task = None
                state.last_memory = None

    def cancel_run(self, chat_id: str) -> bool:
        """Cancel the active run for a chat.

        Returns True if a run was cancelled, False if no active run.
        """
        state = self._chat_runs.get(chat_id)
        if state is None or state.active_task is None or state.active_task.done():
            return False
        logger.info(f"Explicitly cancelling run for chat {chat_id} (run_id={state.run_id})")
        state.active_task.cancel()
        return True

    def get_output_dir(self, chat_id: str) -> Path | None:
        """Get the output directory for a chat's run."""
        state = self._chat_runs.get(chat_id)
        return state.output_dir if state else None

    def pop_last_memory(self, chat_id: str) -> AgentMemory | None:
        """Get and clear the last memory for a chat's run."""
        state = self._chat_runs.get(chat_id)
        if not state:
            return None
        memory = state.last_memory
        state.last_memory = None
        return memory

    def _enqueue_event_threadsafe(
        self,
        event: SubAgentProgressEvent | SubAgentTextEvent | TaskSnapshotEvent,
        event_name: str,
    ) -> None:
        """Thread-safe event enqueueing via call_soon_threadsafe.

        Callbacks may be invoked from thread pool executors, so we must marshal
        the queue operation onto the event loop thread.
        """
        ctx = self._get_context()
        if ctx.event_queue is None or ctx.event_loop is None:
            return

        def _put() -> None:
            if ctx.event_queue is None:
                return
            try:
                ctx.event_queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(f"{event_name} queue full, dropping event")

        ctx.event_loop.call_soon_threadsafe(_put)

    def _on_sub_agent_progress(self, progress: SubAgentProgress) -> None:
        """Callback for sub-agent progress updates.

        Converts the progress to an event and puts it on the queue for streaming.
        """
        event = convert_sub_agent_progress_to_event(progress)
        self._enqueue_event_threadsafe(event, "Sub-agent progress")

    def _on_sub_agent_text(self, text: SubAgentText) -> None:
        """Callback for sub-agent text streaming.

        Converts the text to an event and puts it on the queue for streaming.
        """
        event = SubAgentTextEvent(tool_name=text.tool_name, text=text.text, is_final=text.is_final)
        self._enqueue_event_threadsafe(event, "Sub-agent text")

    def _on_task_snapshot(self, snapshot: list[dict[str, object]]) -> None:
        """Callback for task tracker state changes.

        Puts a TaskSnapshotEvent on the queue for streaming.
        """
        event = TaskSnapshotEvent(tasks=snapshot)
        self._enqueue_event_threadsafe(event, "Task snapshot")

    @staticmethod
    def _drain_queue(
        queue: asyncio.Queue[SubAgentProgressEvent | SubAgentTextEvent | TaskSnapshotEvent],
    ) -> list[SubAgentProgressEvent | SubAgentTextEvent | TaskSnapshotEvent]:
        """Drain all pending events from the queue."""
        events: list[SubAgentProgressEvent | SubAgentTextEvent | TaskSnapshotEvent] = []
        while not queue.empty():
            try:
                events.append(queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        return events

    async def run_agent(
        self,
        chat_id: str,
        prompt: str,
        conversation_history: list[dict[str, Any]],
        rossum_api_token: str,
        rossum_api_base_url: str,
        mcp_mode: Literal["read-only", "read-write"] = "read-only",
        rossum_url: str | None = None,
        images: list[ImageContent] | None = None,
        documents: list[DocumentContent] | None = None,
    ) -> AsyncIterator[StepEvent | StreamDoneEvent | SubAgentProgressEvent | SubAgentTextEvent | TaskSnapshotEvent]:
        """Run the agent with a new prompt.

        Creates a fresh MCP connection, initializes the agent with conversation
        history, and streams step events.

        Yields:
            StepEvent objects during execution, SubAgentProgressEvent for sub-agent progress,
            SubAgentTextEvent for sub-agent text streaming, StreamDoneEvent at the end.
        """
        logger.info(f"Starting agent run with {len(conversation_history)} history messages")
        if images:
            logger.info(f"Including {len(images)} images in the prompt")
        if documents:
            logger.info(f"Including {len(documents)} documents in the prompt")

        run_id = await self._register_run(chat_id)

        ctx = _RequestContext()
        _request_context.set(ctx)

        output_dir = create_session_output_dir()
        set_output_dir(output_dir)
        set_rossum_credentials(rossum_api_base_url, rossum_api_token)
        self._get_chat_run_state(chat_id).output_dir = output_dir
        logger.info(f"Created session output directory: {output_dir}")

        if documents:
            self._save_documents_to_output_dir(documents, output_dir)

        ctx.event_queue = asyncio.Queue(maxsize=100)
        ctx.event_loop = asyncio.get_running_loop()
        set_progress_callback(self._on_sub_agent_progress)
        set_text_callback(self._on_sub_agent_text)
        set_task_tracker(TaskTracker())
        set_task_snapshot_callback(self._on_task_snapshot)

        system_prompt = get_system_prompt()
        url_context = extract_url_context(rossum_url)
        if not url_context.is_empty():
            context_section = format_context_for_prompt(url_context)
            system_prompt = system_prompt + "\n\n---\n" + context_section

        try:
            try:
                async with connect_mcp_server(
                    rossum_api_token=rossum_api_token,
                    rossum_api_base_url=rossum_api_base_url,
                    mcp_mode=mcp_mode,
                ) as mcp_connection:
                    agent = await create_agent(
                        mcp_connection=mcp_connection, system_prompt=system_prompt, config=AgentConfig()
                    )

                    set_mcp_connection(mcp_connection, asyncio.get_event_loop(), mcp_mode)

                    self._restore_conversation_history(agent, conversation_history)

                    total_steps = 0
                    total_input_tokens = 0
                    total_output_tokens = 0

                    user_content = self._build_user_content(prompt, images, documents, output_dir)

                    try:
                        async for step in agent.run(user_content):
                            for sub_event in self._drain_queue(ctx.event_queue):
                                yield sub_event

                            for event in convert_step_to_events(step):
                                yield event

                            if not step.is_streaming:
                                total_steps = step.step_number
                                total_input_tokens = agent._total_input_tokens
                                total_output_tokens = agent._total_output_tokens

                        for sub_event in self._drain_queue(ctx.event_queue):
                            yield sub_event

                        self._get_chat_run_state(chat_id).last_memory = agent.memory

                        yield StreamDoneEvent(
                            total_steps=total_steps,
                            input_tokens=total_input_tokens,
                            output_tokens=total_output_tokens,
                            cache_creation_input_tokens=agent._total_cache_creation_tokens,
                            cache_read_input_tokens=agent._total_cache_read_tokens,
                            token_usage_breakdown=agent.get_token_usage_breakdown(),
                        )
                        agent.log_token_usage_summary()

                    except Exception as e:
                        logger.error(f"Agent execution failed: {e}", exc_info=True)
                        yield StepEvent(
                            type="error",
                            step_number=total_steps + 1,
                            content=f"Agent execution failed: {e}",
                            is_final=True,
                        )
            finally:
                set_progress_callback(None)
                set_text_callback(None)
                set_task_snapshot_callback(None)
                set_task_tracker(None)
                set_output_dir(None)
                set_rossum_credentials(None, None)
        except asyncio.CancelledError:
            logger.info(f"Run cancelled for chat {chat_id} (run_id={run_id})")
            raise
        finally:
            await self._clear_run(chat_id, run_id)

    def _save_documents_to_output_dir(self, documents: list[DocumentContent], output_dir: Path) -> None:
        """Save uploaded documents to the output directory.

        Args:
            documents: List of documents to save.
            output_dir: Path to the session output directory.
        """
        import base64  # noqa: PLC0415 - import here to avoid circular import at module level

        for doc in documents:
            file_path = output_dir / doc.filename
            try:
                file_data = base64.b64decode(doc.data)
                file_path.write_bytes(file_data)
                logger.info(f"Saved document to {file_path}")
            except Exception as e:
                logger.error(f"Failed to save document {doc.filename}: {e}")

    def _build_user_content(
        self,
        prompt: str,
        images: list[ImageContent] | None,
        documents: list[DocumentContent] | None = None,
        output_dir: Path | None = None,
    ) -> UserContent:
        """Build user content for the agent, optionally including images and documents.

        Args:
            prompt: The user's text prompt.
            images: Optional list of images to include.
            documents: Optional list of documents (paths are included in prompt).
            output_dir: Path to the session output directory for resolving document paths.

        Returns:
            Either a plain string (text-only) or a list of content blocks (multimodal).
        """
        if not images and not documents:
            return prompt

        content: list[ImageBlockParam | TextBlockParam] = []
        if images:
            for img in images:
                content.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": img.media_type,
                            "data": img.data,
                        },
                    }
                )
        if documents and output_dir:
            doc_paths = [str(output_dir / doc.filename) for doc in documents]
            doc_info = "\n".join(f"- {path}" for path in doc_paths)
            content.append({"type": "text", "text": f"[Uploaded documents available for processing:\n{doc_info}]"})
        content.append({"type": "text", "text": prompt})
        return content

    def _restore_conversation_history(self, agent: RossumAgent, history: list[dict[str, Any]]) -> None:
        """Restore conversation history to the agent.

        Args:
            agent: The RossumAgent instance.
            history: List of step dicts with 'type' key indicating step type.
                     Supports both new format (with 'type') and legacy format (with 'role').
        """
        if not history:
            return

        first_item = history[0]
        if "type" in first_item and first_item["type"] in ("task_step", "memory_step"):
            agent.memory = AgentMemory.from_dict(history)
        else:
            for msg in history:
                role = msg.get("role")
                content = msg.get("content", "")
                if role == "user":
                    user_content = self._parse_stored_content(content)
                    agent.add_user_message(user_content)
                elif role == "assistant":
                    agent.add_assistant_message(content)

    def _parse_stored_content(self, content: str | list[dict[str, Any]]) -> UserContent:
        """Parse stored content back into UserContent format.

        Args:
            content: Either a string or a list of content block dicts.

        Returns:
            UserContent suitable for the agent.
        """
        if isinstance(content, str):
            return content

        result: list[ImageBlockParam | TextBlockParam] = []
        for block in content:
            block_type = block.get("type")
            if block_type == "image":
                source = block.get("source", {})
                result.append(
                    {
                        "type": "image",
                        "source": {
                            "type": source.get("type", "base64"),
                            "media_type": source.get("media_type", "image/png"),
                            "data": source.get("data", ""),
                        },
                    }
                )
            elif block_type == "text":
                result.append({"type": "text", "text": block.get("text", "")})

        return result if result else ""

    def build_updated_history(
        self,
        existing_history: list[dict[str, Any]],
        user_prompt: str,
        final_response: str | None,
        images: list[ImageContent] | None = None,
        documents: list[DocumentContent] | None = None,
        memory: AgentMemory | None = None,
    ) -> list[dict[str, Any]]:
        """Build updated conversation history after agent execution.

        Stores task steps and assistant text responses, but strips out tool calls
        and tool results to keep context lean for multi-turn conversations.

        Args:
            existing_history: Previous conversation history (ignored if memory available).
            user_prompt: The user's prompt that was just processed.
            final_response: The agent's final response, if any.
            images: Optional list of images included with the user prompt.
            documents: Optional list of documents included with the user prompt.
            memory: Optional agent memory from the completed run.
        """
        if memory is not None:
            lean_history: list[dict[str, Any]] = []
            for step_dict in memory.to_dict():
                if step_dict.get("type") == "task_step":
                    lean_history.append(step_dict)
                elif step_dict.get("type") == "memory_step":
                    text = step_dict.get("text")
                    thinking_blocks = step_dict.get("thinking_blocks", [])
                    if text or thinking_blocks:
                        lean_history.append(
                            {
                                "type": "memory_step",
                                "step_number": step_dict.get("step_number", 0),
                                "text": text,
                                "tool_calls": [],
                                "tool_results": [],
                                "thinking_blocks": thinking_blocks,
                            }
                        )
            return lean_history

        updated = list(existing_history)
        user_content = self._build_user_content(user_prompt, images)
        if documents:
            doc_names = ", ".join(doc.filename for doc in documents)
            if isinstance(user_content, str):
                user_content = f"[Uploaded documents: {doc_names}]\n\n{user_content}"
            else:
                user_content.insert(0, {"type": "text", "text": f"[Uploaded documents: {doc_names}]"})
        updated.append({"role": "user", "content": user_content})
        if final_response:
            updated.append({"role": "assistant", "content": final_response})
        return updated
