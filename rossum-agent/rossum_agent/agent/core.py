"""Core agent module implementing the RossumAgent class with Anthropic tool use API.

This module provides the main agent loop for interacting with the Rossum platform
using Claude models via AWS Bedrock and MCP tools.

Streaming Architecture & AgentStep Yield Points
================================================

The agent streams responses via `_stream_model_response` which yields `AgentStep` objects
at multiple points to provide real-time updates to the client. The yield flow is:

    _stream_model_response
        │
        ├── #5 forwards from _process_stream_events ──┬── #1 Timeout flush (buffer stale after 1.5s)
        │                                             ├── #2 Stream end flush (final text)
        │                                             ├── #3 Thinking tokens (chain-of-thought)
        │                                             └── #4 Text deltas (after initial buffer)
        │
        ├── #6 Final answer (no tools, response complete)
        │
        └── #7 forwards from _execute_tools_with_progress
                ├── Tool starting (which tool is about to run)
                └── Sub-agent progress (from nested agent tools like patch_schema_with_subagent)

Key concepts:
- Uses AsyncAnthropicBedrock with async streaming (no thread pool bridge)
- _process_stream_events uses asyncio.wait on anext() for timeout-based buffer flushing
- Initial text buffering (INITIAL_TEXT_BUFFER_DELAY=1.5s) allows determining step type
  (INTERMEDIATE vs FINAL_ANSWER) before streaming to client
- After initial flush, text tokens stream immediately
- Tool execution yields progress updates for UI responsiveness
- In a single step, a thinking block is always followed by an intermediate block
  (tool calls or text response)
"""

from __future__ import annotations

import asyncio
import dataclasses
import difflib
import json
import logging
import queue
import random
import time
from contextvars import copy_context
from functools import partial
from typing import TYPE_CHECKING, ClassVar

from anthropic import APIError, APITimeoutError, RateLimitError
from anthropic._types import Omit
from anthropic.types import (
    ContentBlockStopEvent,
    InputJSONDelta,
    Message,
    MessageParam,
    MessageStreamEvent,
    RawContentBlockDeltaEvent,
    RawContentBlockStartEvent,
    TextBlockParam,
    TextDelta,
    ThinkingBlock,
    ThinkingConfigAdaptiveParam,
    ThinkingDelta,
    ToolParam,
    ToolUseBlock,
)
from pydantic import BaseModel

from rossum_agent.agent.memory import AgentMemory, MemoryStep
from rossum_agent.agent.models import (
    AgentConfig,
    AgentStep,
    ErrorStep,
    FinalAnswerStep,
    StepType,
    StreamDelta,
    TextDeltaStep,
    ThinkingBlockData,
    ThinkingStep,
    ToolCall,
    ToolResult,
    ToolResultStep,
    ToolStartStep,
    truncate_content,
)
from rossum_agent.agent.spillover import maybe_spill
from rossum_agent.api.models.schemas import TokenUsageBreakdown
from rossum_agent.bedrock_client import create_async_bedrock_client, get_model_id
from rossum_agent.rossum_mcp_integration import (
    classify_operation,
    extract_entity_id,
    extract_entity_type,
    mcp_tools_to_anthropic_format,
)
from rossum_agent.tools import (
    INTERNAL_WRITE_TOOL_NAMES,
    execute_internal_tool,
    get_internal_tool_names,
    get_internal_tools,
)
from rossum_agent.tools.core import (
    CAUTIOUS_APPROVAL_LABEL,
    CAUTIOUS_CONFIRMATION_MARKER,
    AgentContext,
    AgentQuestion,
    AgentQuestionItem,
    QuestionOption,
    SubAgentProgress,
    SubAgentTokenUsage,
    get_context,
    set_context,
)
from rossum_agent.tools.dynamic_tools import (
    DELETE_TOOL_NAME,
    DISCOVERY_TOOL_NAME,
    get_dynamic_tools,
    get_tools_version,
    is_mcp_write_tool,
    preload_categories_for_request,
    reset_dynamic_tools,
)
from rossum_agent.utils import add_message_cache_breakpoint

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from anthropic import AsyncAnthropicBedrock

    from rossum_agent.agent.types import UserContent
    from rossum_agent.rossum_mcp_integration import MCPConnection

logger = logging.getLogger(__name__)

RATE_LIMIT_MAX_RETRIES = 5
RATE_LIMIT_BASE_DELAY = 2.0
RATE_LIMIT_MAX_DELAY = 60.0

# Buffer text tokens for this duration before first flush to allow time to determine
# whether this is an intermediate step (with tool calls) or final answer text.
# This delay helps correctly classify the step type before streaming to the client.
INITIAL_TEXT_BUFFER_DELAY = 1.5

# Sentinel for detecting async generator exhaustion in anext()
_STREAM_END = object()


def _parse_json_encoded_strings(arguments: dict) -> dict:
    """Recursively parse JSON-encoded strings in tool arguments.

    LLMs sometimes generate JSON-encoded strings for list/dict arguments instead of
    actual lists/dicts. This function detects and parses such strings.

    For example, converts:
        {"fields_to_keep": "[\"a\", \"b\"]"}
    To:
        {"fields_to_keep": ["a", "b"]}
    """
    # Parameters that should remain as JSON strings (not parsed to lists/dicts)
    keep_as_string = {"changes"}

    result = {}
    for key, value in arguments.items():
        if key in keep_as_string:
            result[key] = value
        elif isinstance(value, str) and value.startswith(("[", "{")):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, (list, dict)):
                    result[key] = parsed
                else:
                    result[key] = value
            except json.JSONDecodeError:
                result[key] = value
        elif isinstance(value, dict):
            result[key] = _parse_json_encoded_strings(value)
        else:
            result[key] = value
    return result


def _tool_call_fingerprint(tool_call: ToolCall) -> str:
    """Create a stable fingerprint for deduplicating identical tool calls in one step."""
    return json.dumps(
        {"name": tool_call.name, "arguments": tool_call.arguments},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _deduplicate_tool_calls(
    tool_calls: list[ToolCall], step_num: int
) -> tuple[list[ToolCall], dict[str, list[ToolCall]]]:
    """Deduplicate identical tool calls, returning unique calls and a map of duplicates by primary ID."""
    deduped: list[ToolCall] = []
    duplicate_calls_by_id: dict[str, list[ToolCall]] = {}
    seen_fingerprints: dict[str, ToolCall] = {}

    for tool_call in tool_calls:
        fingerprint = _tool_call_fingerprint(tool_call)
        primary_call = seen_fingerprints.get(fingerprint)
        if primary_call is None:
            seen_fingerprints[fingerprint] = tool_call
            deduped.append(tool_call)
            duplicate_calls_by_id[tool_call.id] = []
        else:
            duplicate_calls_by_id[primary_call.id].append(tool_call)

    duplicate_count = len(tool_calls) - len(deduped)
    if duplicate_count > 0:
        logger.info(
            "Step %s: deduplicated %s duplicate tool call(s) (%s requested, %s executed)",
            step_num,
            duplicate_count,
            len(tool_calls),
            len(deduped),
        )

    return deduped, duplicate_calls_by_id


class _SchemaStagger:
    """Stagger schema patch calls to avoid 412 conflicts from concurrent writes."""

    _TOOLS: ClassVar[set[str]] = {"patch_schema", "patch_schema_with_subagent"}
    _DELAY_SECONDS = 0.5

    def __init__(self) -> None:
        self._counter = 0

    async def maybe_delay(self, tool_name: str) -> None:
        if tool_name not in self._TOOLS:
            return
        delay = self._counter * self._DELAY_SECONDS
        self._counter += 1
        if delay > 0:
            logger.info("Staggering %s by %.1fs to avoid conflicts", tool_name, delay)
            await asyncio.sleep(delay)


# How often to log streaming progress (seconds)
_STREAM_PROGRESS_LOG_INTERVAL = 10.0


@dataclasses.dataclass
class _StreamState:
    """Mutable state for streaming model response.

    Attributes:
        first_text_token_time: Timestamp of when the first text token was received.
            Used to implement initial buffering delay (see INITIAL_TEXT_BUFFER_DELAY).
        initial_buffer_flushed: Whether the initial buffer has been flushed after
            the delay period. Once True, text tokens are streamed immediately.
    """

    thinking_text: str = ""
    response_text: str = ""
    final_message: Message | None = None
    text_buffer: list[str] = dataclasses.field(default_factory=list)
    tool_calls: list[ToolCall] = dataclasses.field(default_factory=list)
    pending_tools: dict[int, dict[str, str]] = dataclasses.field(default_factory=dict)
    first_text_token_time: float | None = None
    initial_buffer_flushed: bool = False
    thinking_finalized: bool = False
    # Streaming progress tracking
    stream_start_time: float = dataclasses.field(default_factory=time.monotonic)
    last_progress_log_time: float = dataclasses.field(default_factory=time.monotonic)
    thinking_deltas: int = 0
    text_deltas: int = 0

    def _should_flush_initial_buffer(self) -> bool:
        """Check if the initial buffer delay has elapsed and buffer should be flushed."""
        if self.initial_buffer_flushed:
            return True
        if self.first_text_token_time is None:
            return False
        return (time.monotonic() - self.first_text_token_time) >= INITIAL_TEXT_BUFFER_DELAY

    def get_step_type(self) -> StepType:
        """Get the step type based on whether tool calls are pending."""
        return StepType.INTERMEDIATE if self.pending_tools or self.tool_calls else StepType.FINAL_ANSWER

    def flush_buffer(self, step_num: int, step_type: StepType) -> TextDeltaStep | None:
        """Flush text buffer and return TextDeltaStep if buffer had content."""
        if not self.text_buffer:
            return None
        buffered_text = "".join(self.text_buffer)
        self.text_buffer.clear()
        self.response_text += buffered_text
        return TextDeltaStep(
            step_number=step_num,
            step_type=step_type,
            text_delta=buffered_text,
            accumulated_text=self.response_text,
            thinking=self.thinking_text or None,
        )

    def finalize_thinking(self, step_num: int) -> ThinkingStep | None:
        """Return a finalized ThinkingStep if thinking exists and hasn't been finalized yet."""
        if not self.thinking_text or self.thinking_finalized:
            return None
        self.thinking_finalized = True
        return ThinkingStep(step_number=step_num, thinking=self.thinking_text, is_streaming=False)

    def maybe_log_progress(self, step_num: int) -> None:
        """Log streaming progress periodically (every _STREAM_PROGRESS_LOG_INTERVAL seconds)."""
        now = time.monotonic()
        if now - self.last_progress_log_time < _STREAM_PROGRESS_LOG_INTERVAL:
            return
        self.last_progress_log_time = now
        elapsed = now - self.stream_start_time
        phase = "thinking" if not self.text_deltas else "text"
        thinking_chars = len(self.thinking_text)
        text_chars = len(self.response_text) + sum(len(t) for t in self.text_buffer)
        total_chars = thinking_chars + text_chars
        chars_per_sec = total_chars / elapsed if elapsed > 0 else 0
        logger.info(
            f"Step {step_num} streaming [{phase}]: {elapsed:.0f}s elapsed, "
            f"chars={total_chars} ({chars_per_sec:.0f}/s), "
            f"thinking={thinking_chars} chars, text={text_chars} chars"
        )


@dataclasses.dataclass
class TokenTracker:
    """Tracks all token usage (main agent + sub-agents) in one place."""

    main_input: int = 0
    main_output: int = 0
    sub_input: int = 0
    sub_output: int = 0
    main_cache_creation: int = 0
    main_cache_read: int = 0
    sub_cache_creation: int = 0
    sub_cache_read: int = 0
    sub_by_tool: dict[str, tuple[int, int]] = dataclasses.field(default_factory=dict)
    sub_cache_by_tool: dict[str, tuple[int, int]] = dataclasses.field(default_factory=dict)

    @property
    def total_input(self) -> int:
        return self.main_input + self.sub_input

    @property
    def total_output(self) -> int:
        return self.main_output + self.sub_output

    @property
    def total_cache_creation(self) -> int:
        return self.main_cache_creation + self.sub_cache_creation

    @property
    def total_cache_read(self) -> int:
        return self.main_cache_read + self.sub_cache_read

    def accumulate_main(self, input_tokens: int, output_tokens: int, cache_creation: int, cache_read: int) -> None:
        self.main_input += input_tokens
        self.main_output += output_tokens
        self.main_cache_creation += cache_creation
        self.main_cache_read += cache_read

    def accumulate_sub(self, usage: SubAgentTokenUsage) -> None:
        self.sub_input += usage.input_tokens
        self.sub_output += usage.output_tokens
        prev_in, prev_out = self.sub_by_tool.get(usage.tool_name, (0, 0))
        self.sub_by_tool[usage.tool_name] = (prev_in + usage.input_tokens, prev_out + usage.output_tokens)
        self.sub_cache_creation += usage.cache_creation_input_tokens
        self.sub_cache_read += usage.cache_read_input_tokens
        prev_cc, prev_cr = self.sub_cache_by_tool.get(usage.tool_name, (0, 0))
        self.sub_cache_by_tool[usage.tool_name] = (
            prev_cc + usage.cache_creation_input_tokens,
            prev_cr + usage.cache_read_input_tokens,
        )

    def to_breakdown(self) -> TokenUsageBreakdown:
        return TokenUsageBreakdown.from_raw_counts(
            total_input=self.total_input,
            total_output=self.total_output,
            main_input=self.main_input,
            main_output=self.main_output,
            sub_input=self.sub_input,
            sub_output=self.sub_output,
            sub_by_tool=self.sub_by_tool,
            main_cache_creation=self.main_cache_creation,
            main_cache_read=self.main_cache_read,
            sub_cache_creation=self.sub_cache_creation,
            sub_cache_read=self.sub_cache_read,
            sub_cache_by_tool=self.sub_cache_by_tool,
        )


class RossumAgent:
    """Claude-powered agent for Rossum document processing.

    This agent uses Anthropic's tool use API to interact with the Rossum platform
    via MCP tools. It maintains conversation state across multiple turns and
    supports streaming responses.

    Memory is stored as structured MemoryStep objects and rebuilt into messages
    each call.
    """

    def __init__(
        self,
        client: AsyncAnthropicBedrock,
        mcp_connection: MCPConnection,
        system_prompt: str,
        config: AgentConfig | None = None,
        additional_tools: list[ToolParam] | None = None,
    ) -> None:
        self.client = client
        self.mcp_connection = mcp_connection
        self.system_prompt = system_prompt
        self.config = config or AgentConfig()
        self.additional_tools = additional_tools or []

        self.memory = AgentMemory()
        self._tools_cache: list[ToolParam] | None = None
        self._tools_cache_version: int = -1
        self.tokens = TokenTracker()

    @property
    def messages(self) -> list[MessageParam]:
        """Get the current conversation messages (rebuilt from memory)."""
        return self.memory.write_to_messages()

    def reset(self) -> None:
        """Reset the agent's conversation state."""
        self.memory.reset()
        self.tokens = TokenTracker()
        reset_dynamic_tools()

    def get_token_usage_breakdown(self) -> TokenUsageBreakdown:
        """Get token usage breakdown by agent vs sub-agents."""
        return self.tokens.to_breakdown()

    def log_token_usage_summary(self) -> None:
        """Log a human-readable token usage summary."""
        breakdown = self.get_token_usage_breakdown()
        logger.info("\n".join(breakdown.format_summary_lines()))

    def add_user_message(self, content: UserContent) -> None:
        """Add a user message to the conversation history."""
        self.memory.add_task(content)

    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message to the conversation history.

        This creates a MemoryStep with text set, which ensures the
        message is properly serialized when rebuilding conversation history.
        For proper conversation flow with tool use, use the run() method instead.
        """
        step = MemoryStep(step_number=0, text=content)
        self.memory.add_step(step)

    async def _get_tools(self) -> list[ToolParam]:
        """Get all available tools in Anthropic format.

        Initially loads only the discovery tool from MCP (list_tool_categories)
        plus internal tools. Additional MCP tools are loaded dynamically via
        load_tool.
        """
        current_version = get_tools_version()
        if self._tools_cache is None or self._tools_cache_version != current_version:
            mcp_tools = await self.mcp_connection.get_tools()
            always_loaded_names = {DISCOVERY_TOOL_NAME}
            if not get_context().is_read_only:
                always_loaded_names.add(DELETE_TOOL_NAME)
            always_loaded = [t for t in mcp_tools if t.name in always_loaded_names]
            self._tools_cache = (
                mcp_tools_to_anthropic_format(always_loaded) + get_internal_tools() + self.additional_tools
            )
            self._tools_cache_version = current_version
        # Include dynamically loaded tools
        return self._tools_cache + get_dynamic_tools()

    def _serialize_tool_result(self, result: object) -> str:
        """Serialize a tool result to a string for storage in context.

        Handles pydantic models, dataclasses, dicts, lists, and other objects properly.
        """
        if result is None:
            return "Tool executed successfully (no output)"

        # Handle dataclasses (check before pydantic since pydantic models aren't dataclasses)
        if dataclasses.is_dataclass(result) and not isinstance(result, type):
            return json.dumps(dataclasses.asdict(result), separators=(",", ":"), default=str)

        # Handle lists of dataclasses
        if isinstance(result, list) and result and dataclasses.is_dataclass(result[0]):
            return json.dumps(
                [
                    dataclasses.asdict(item)
                    for item in result
                    if dataclasses.is_dataclass(item) and not isinstance(item, type)
                ],
                separators=(",", ":"),
                default=str,
            )

        # Handle pydantic models
        # Use mode='json' to ensure nested models are properly serialized to JSON-compatible dicts
        if isinstance(result, BaseModel):
            return json.dumps(result.model_dump(mode="json"), separators=(",", ":"), default=str)

        # Handle lists of pydantic models
        if isinstance(result, list) and result and isinstance(result[0], BaseModel):
            return json.dumps(
                [item.model_dump(mode="json") for item in result if isinstance(item, BaseModel)],
                separators=(",", ":"),
                default=str,
            )

        # Handle dicts and regular lists
        if isinstance(result, dict | list):
            return json.dumps(result, separators=(",", ":"), default=str)

        # Fallback to string representation
        return str(result)

    def _process_stream_event(
        self, event: MessageStreamEvent, pending_tools: dict[int, dict[str, str]], tool_calls: list[ToolCall]
    ) -> StreamDelta | None:
        """Process a single stream event.

        Returns:
            StreamDelta with kind="thinking" or "text", or None if no delta.
        """
        if isinstance(event, RawContentBlockStartEvent):
            if isinstance(event.content_block, ToolUseBlock):
                pending_tools[event.index] = {
                    "name": event.content_block.name,
                    "id": event.content_block.id,
                    "json": "",
                }

        elif isinstance(event, RawContentBlockDeltaEvent):
            if isinstance(event.delta, ThinkingDelta):
                return StreamDelta(kind="thinking", content=event.delta.thinking)
            if isinstance(event.delta, TextDelta):
                return StreamDelta(kind="text", content=event.delta.text)
            if isinstance(event.delta, InputJSONDelta) and event.index in pending_tools:
                pending_tools[event.index]["json"] += event.delta.partial_json

        elif isinstance(event, ContentBlockStopEvent) and event.index in pending_tools:
            tool_info = pending_tools.pop(event.index)
            try:
                arguments = json.loads(tool_info["json"]) if tool_info["json"] else {}
                arguments = _parse_json_encoded_strings(arguments)
            except json.JSONDecodeError as e:
                logger.warning("Failed to decode tool arguments for %s: %s", tool_info["name"], e)
                arguments = {}
            tool_calls.append(ToolCall(id=tool_info["id"], name=tool_info["name"], arguments=arguments))

        return None

    def _extract_thinking_blocks(self, message: Message) -> list[ThinkingBlockData]:
        """Extract thinking blocks from a message for preserving in conversation history."""
        return [
            ThinkingBlockData(thinking=block.thinking, signature=block.signature)
            for block in message.content
            if isinstance(block, ThinkingBlock)
        ]

    def _handle_text_delta(self, step_num: int, content: str, state: _StreamState) -> TextDeltaStep | None:
        """Handle a text delta, buffering or flushing as appropriate."""
        if state.first_text_token_time is None:
            state.first_text_token_time = time.monotonic()
        else:
            if time.monotonic() - state.first_text_token_time > INITIAL_TEXT_BUFFER_DELAY:
                state.initial_buffer_flushed = True

        state.text_buffer.append(content)

        if state.initial_buffer_flushed:
            return state.flush_buffer(step_num, state.get_step_type())
        if state.pending_tools or state.tool_calls:
            state.initial_buffer_flushed = True
            return state.flush_buffer(step_num, StepType.INTERMEDIATE)
        return None

    def _handle_text_delta_with_finalization(
        self, step_num: int, content: str, state: _StreamState
    ) -> list[AgentStep]:
        """Finalize thinking (if needed) then handle text delta. Returns 0-2 steps."""
        steps: list[AgentStep] = []
        if finalized := state.finalize_thinking(step_num):
            steps.append(finalized)
        if text_step := self._handle_text_delta(step_num, content, state):
            steps.append(text_step)
        return steps

    async def _process_stream_events(
        self,
        step_num: int,
        stream: AsyncIterator[MessageStreamEvent],
        state: _StreamState,
    ) -> AsyncIterator[AgentStep]:
        """Process stream events and yield AgentSteps.

        Text tokens are buffered for INITIAL_TEXT_BUFFER_DELAY seconds after the first
        text token is received. This allows time to determine whether the response will
        include tool calls (intermediate step) or is a final answer, enabling correct
        step type classification before streaming to the client.

        After the initial buffer is flushed, subsequent text tokens are streamed immediately.

        Uses asyncio.wait with timeout on anext() to implement buffer flush during model
        pauses without cancelling the underlying stream read.
        """
        pending_next: asyncio.Task | None = None
        try:
            while True:
                if pending_next is None:
                    pending_next = asyncio.ensure_future(anext(stream, _STREAM_END))

                done, _ = await asyncio.wait({pending_next}, timeout=INITIAL_TEXT_BUFFER_DELAY)

                if not done:
                    # Yield #1: Timeout-based flush of initial text buffer (ensures responsiveness during model pauses)
                    if (
                        state.text_buffer
                        and state._should_flush_initial_buffer()
                        and (step := state.flush_buffer(step_num, state.get_step_type()))
                    ):
                        state.initial_buffer_flushed = True
                        yield step
                    continue

                item = pending_next.result()
                pending_next = None

                if item is _STREAM_END:
                    # Yield #2: Stream ended - flush any remaining buffered text
                    if step := state.flush_buffer(step_num, state.get_step_type()):
                        yield step
                    break

                event: MessageStreamEvent = item  # type: ignore[assignment]  # narrowed after _STREAM_END sentinel check
                delta = self._process_stream_event(event, state.pending_tools, state.tool_calls)
                if not delta:
                    continue

                if delta.kind == "thinking":
                    state.thinking_text += delta.content
                    state.thinking_deltas += 1
                    state.first_text_token_time = state.first_text_token_time or time.monotonic()
                    state.maybe_log_progress(step_num)
                    # Yield #3: Streaming thinking tokens (extended thinking / chain-of-thought)
                    yield ThinkingStep(
                        step_number=step_num,
                        thinking=state.thinking_text,
                    )
                    continue

                state.text_deltas += 1
                state.maybe_log_progress(step_num)
                # Yield #4a: Finalize thinking before first text delta.
                # Yield #4b: Text delta - immediate flush after initial buffer period or when tool calls detected.
                for yielded_step in self._handle_text_delta_with_finalization(step_num, delta.content, state):
                    yield yielded_step
        finally:
            if pending_next is not None and not pending_next.done():
                pending_next.cancel()

    async def _stream_model_response(self, step_num: int) -> AsyncIterator[AgentStep]:
        """Stream model response, yielding partial steps as thinking streams in.

        Extended thinking separates the model's internal reasoning (thinking blocks)
        from its final response (text blocks). This allows distinguishing between
        the chain-of-thought process and the actual answer.

        Yields:
            AgentStep objects - partial steps while streaming, then final step with tool results.
        """
        messages = self.memory.write_to_messages()
        tools = await self._get_tools()
        model_id = get_model_id()
        state = _StreamState()
        logger.info(f"Step {step_num}: streaming started (model={model_id}, messages={len(messages)})")

        thinking_config: ThinkingConfigAdaptiveParam = {"type": "adaptive"}

        # Cache breakpoints: system prompt
        system: list[TextBlockParam] = [
            {"type": "text", "text": self.system_prompt, "cache_control": {"type": "ephemeral"}}
        ]

        # Cache breakpoints: last tool definition
        if tools:
            tools = [*tools]  # shallow copy
            tools[-1] = {**tools[-1], "cache_control": {"type": "ephemeral"}}  # type: ignore[assignment]  # runtime addition of cache_control

        # Cache breakpoints: last message content block
        add_message_cache_breakpoint(messages)  # type: ignore[arg-type]  # MessageParam is dict at runtime

        async with self.client.messages.stream(
            model=model_id,
            max_tokens=self.config.max_output_tokens,
            system=system,
            messages=messages,
            tools=tools if tools else Omit(),
            thinking=thinking_config,
            temperature=self.config.temperature,
            output_config={"effort": self.config.effort},
        ) as stream:
            # Yield #5: Forward all streaming steps from _process_stream_events (yields #1-4)
            async for step in self._process_stream_events(step_num, stream, state):  # type: ignore[arg-type]  # AsyncMessageStream implements AsyncIterator protocol
                yield step
            state.final_message = await stream.get_final_message()

        if state.final_message is None:
            raise RuntimeError("Stream ended without final message")

        thinking_blocks = self._extract_thinking_blocks(state.final_message)
        raw_input_tokens = state.final_message.usage.input_tokens
        output_tokens = state.final_message.usage.output_tokens
        cache_creation = getattr(state.final_message.usage, "cache_creation_input_tokens", 0) or 0
        cache_read = getattr(state.final_message.usage, "cache_read_input_tokens", 0) or 0
        input_tokens = raw_input_tokens + cache_creation + cache_read
        self.tokens.accumulate_main(input_tokens, output_tokens, cache_creation, cache_read)
        stream_elapsed = time.monotonic() - state.stream_start_time
        logger.info(
            f"Step {step_num}: completed in {stream_elapsed:.1f}s, "
            f"input_tokens={input_tokens}, output_tokens={output_tokens}, "
            f"cache_creation={cache_creation}, cache_read={cache_read}, "
            f"total_input={self.tokens.total_input}, total_output={self.tokens.total_output}"
        )

        # Yield #6: Finalize thinking if not already done (e.g. thinking → tool_use with no text)
        if finalized := state.finalize_thinking(step_num):
            yield finalized

        # Yield #7: Finalized text event that corrects misclassification.
        # During streaming, text may have been classified as final_answer before tool_use
        # blocks arrived. Now that tool_calls is fully populated, emit the authoritative
        # intermediate classification. Only needed when tool calls exist — otherwise
        # FinalAnswerStep (yield #8) already serves as the finalization event.
        if state.response_text and state.tool_calls:
            yield TextDeltaStep(
                step_number=step_num,
                step_type=StepType.INTERMEDIATE,
                text_delta="",
                accumulated_text=state.response_text,
                is_streaming=False,
            )

        if not state.tool_calls:
            memory_step = MemoryStep(
                step_number=step_num,
                text=state.response_text if state.response_text else None,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
            self.memory.add_step(memory_step)
            # Yield #8: Final answer step (no tool calls, response complete)
            yield FinalAnswerStep(
                step_number=step_num,
                final_answer=state.response_text or "",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
            return

        # Yield #9: Forward tool execution progress steps from _execute_tools_with_progress
        async for step_or_result in self._execute_tools_with_progress(
            step_num,
            response_text=state.response_text,
            tool_calls=state.tool_calls,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            thinking_blocks=thinking_blocks,
        ):
            yield step_or_result

    async def _execute_tools_with_progress(
        self,
        step_num: int,
        response_text: str,
        tool_calls: list[ToolCall],
        input_tokens: int,
        output_tokens: int,
        thinking_blocks: list[ThinkingBlockData] | None = None,
    ) -> AsyncIterator[ToolStartStep | ToolResultStep]:
        """Execute tools in parallel and yield progress updates."""
        memory_step = MemoryStep(
            step_number=step_num,
            text=response_text or None,
            tool_calls=tool_calls,
            thinking_blocks=thinking_blocks or [],
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        deduped_tool_calls, duplicate_calls_by_id = _deduplicate_tool_calls(tool_calls, step_num)
        total_tools = len(deduped_tool_calls)

        yield ToolStartStep(
            step_number=step_num,
            tool_calls=deduped_tool_calls,
            tool_progress=(0, total_tools),
        )

        progress_queue: asyncio.Queue[ToolStartStep] = asyncio.Queue()
        results_by_id: dict[str, ToolResult] = {}

        # Stagger schema patch calls to avoid 412 conflicts from concurrent writes
        stagger = _SchemaStagger()

        async def execute_single_tool(tool_call: ToolCall, duplicate_calls: list[ToolCall], idx: int) -> None:
            await stagger.maybe_delay(tool_call.name)

            tool_progress = (idx, total_tools)
            async for progress_or_result in self._execute_tool_with_progress(
                tool_call, step_num, deduped_tool_calls, tool_progress
            ):
                if isinstance(progress_or_result, ToolStartStep):
                    await progress_queue.put(progress_or_result)
                elif isinstance(progress_or_result, ToolResult):
                    results_by_id[tool_call.id] = progress_or_result
                    for duplicate_call in duplicate_calls:
                        results_by_id[duplicate_call.id] = ToolResult(
                            tool_call_id=duplicate_call.id,
                            name=duplicate_call.name,
                            content=progress_or_result.content,
                            is_error=progress_or_result.is_error,
                        )

        tasks = [
            asyncio.create_task(execute_single_tool(tool_call, duplicate_calls_by_id[tool_call.id], idx))
            for idx, tool_call in enumerate(deduped_tool_calls, 1)
        ]

        try:
            pending = set(tasks)
            while pending:
                _done, pending = await asyncio.wait(pending, timeout=0.05, return_when=asyncio.FIRST_COMPLETED)

                while not progress_queue.empty():
                    yield progress_queue.get_nowait()

            while not progress_queue.empty():
                yield progress_queue.get_nowait()
        except asyncio.CancelledError:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise

        memory_results = [results_by_id[tc.id] for tc in tool_calls if tc.id in results_by_id]
        streamed_results = [results_by_id[tc.id] for tc in deduped_tool_calls if tc.id in results_by_id]
        memory_step.tool_results = memory_results
        self.memory.add_step(memory_step)

        yield ToolResultStep(
            step_number=step_num,
            tool_calls=deduped_tool_calls,
            tool_results=streamed_results,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def _drain_token_queue(self, token_queue: queue.Queue[SubAgentTokenUsage]) -> None:
        """Drain all pending token usage from the queue."""
        while True:
            try:
                usage = token_queue.get_nowait()
                self.tokens.accumulate_sub(usage)
                logger.info(
                    f"Sub-agent '{usage.tool_name}' token usage (iter {usage.iteration}): "
                    f"in={usage.input_tokens}, out={usage.output_tokens}, "
                    f"cumulative total: in={self.tokens.total_input}, out={self.tokens.total_output}"
                )
            except queue.Empty:
                break

    @staticmethod
    def _is_write_tool(name: str) -> bool:
        """Check if a tool is a write operation (MCP or internal)."""
        return name in INTERNAL_WRITE_TOOL_NAMES or is_mcp_write_tool(name)

    async def _check_cautious_write_gate(self, tool_call: ToolCall, agent_ctx: AgentContext) -> ToolResult | None:
        """Gate write tools behind user confirmation for cautious persona.

        For update/patch operations, fetches the existing object and shows a
        field-level diff instead of raw arguments.

        Returns a ToolResult (blocking the tool) if confirmation is needed,
        or None if the tool should proceed.
        """
        if agent_ctx.persona != "cautious":
            return None
        if not self._is_write_tool(tool_call.name):
            return None
        if tool_call.name in agent_ctx.cautious_preapproved_writes:
            agent_ctx.cautious_preapproved_writes.discard(tool_call.name)
            logger.info(f"Cautious persona: allowing pre-approved write tool {tool_call.name}")
            return None

        # Block the tool and ask the user for confirmation
        agent_ctx.cautious_blocked_writes.add(tool_call.name)

        change_preview = await self._build_change_preview(tool_call)
        agent_ctx.report_question(
            AgentQuestion(
                questions=[
                    AgentQuestionItem(
                        question=(
                            f"The agent wants to execute write operation **{tool_call.name}**\n\n"
                            f"{change_preview}\n\n"
                            "Do you want to proceed?"
                        ),
                        options=[
                            QuestionOption(value="yes", label=CAUTIOUS_APPROVAL_LABEL),
                            QuestionOption(value="no", label="No, cancel"),
                            QuestionOption(value="chat", label="Let me provide context"),
                        ],
                    )
                ]
            )
        )

        logger.info(f"Cautious persona: blocked write tool {tool_call.name}, asking user for confirmation")
        return ToolResult(
            tool_call_id=tool_call.id,
            name=tool_call.name,
            content=(
                f"Write operation `{tool_call.name}` {CAUTIOUS_CONFIRMATION_MARKER} (cautious persona). "
                "Waiting for user response. STOP — do not call other tools or produce text in the same turn."
            ),
            is_error=True,
        )

    async def _build_change_preview(self, tool_call: ToolCall) -> str:
        """Build a human-readable change preview for a write tool call.

        For MCP update/patch operations, fetches the existing entity and shows
        a field-level diff. Falls back to raw arguments for other operations.
        """
        args = tool_call.arguments
        entity_type = extract_entity_type(tool_call.name)
        entity_id = extract_entity_id(entity_type or "", args) if entity_type else None
        operation = classify_operation(tool_call.name)

        # Only fetch existing object for update operations on identifiable entities
        if operation == "update" and entity_type and entity_id and self.mcp_connection:
            existing = await self.mcp_connection.fetch_snapshot(entity_type, entity_id)
            if existing is not None:
                return self._format_field_diff(existing, args, entity_type, entity_id)

        # Fallback: raw arguments
        args_json = json.dumps(args, indent=2, ensure_ascii=False)
        return f"**Arguments:**\n```json\n{args_json}\n```"

    @staticmethod
    def _extract_update_fields(arguments: dict, entity_type: str) -> dict:
        """Extract the fields being changed from tool arguments.

        Handles both flat args (update_hook: hook_id, name, active, ...) and
        nested data objects (update_queue: queue_id, queue_data={...}).
        """
        id_key = f"{entity_type}_id"
        update_fields: dict = {}

        for key, value in arguments.items():
            if key in (id_key, "id"):
                continue
            if value is None:
                continue
            # Nested data object (e.g. queue_data, engine_data) — flatten it
            if isinstance(value, dict) and key.endswith("_data"):
                update_fields.update(value)
            else:
                update_fields[key] = value

        return update_fields

    @staticmethod
    def _format_field_diff(existing: dict, arguments: dict, entity_type: str, entity_id: str) -> str:
        """Format a unified diff between existing object and proposed changes."""
        update_fields = RossumAgent._extract_update_fields(arguments, entity_type)

        if not update_fields:
            args_json = json.dumps(arguments, indent=2, ensure_ascii=False)
            return f"**Arguments:**\n```json\n{args_json}\n```"

        # Build the "after" object by applying updates to the existing state
        after = {**existing, **update_fields}

        before_lines = json.dumps(existing, indent=2, ensure_ascii=False).splitlines(keepends=True)
        after_lines = json.dumps(after, indent=2, ensure_ascii=False).splitlines(keepends=True)

        diff_lines = list(difflib.unified_diff(before_lines, after_lines, fromfile="current", tofile="proposed", n=2))

        if not diff_lines:
            return f"**No effective changes to {entity_type} {entity_id}**"

        diff_text = "".join(diff_lines)
        return f"**Changes to {entity_type} {entity_id}:**\n```diff\n{diff_text}```"

    async def _execute_tool_with_progress(
        self, tool_call: ToolCall, step_num: int, tool_calls: list[ToolCall], tool_progress: tuple[int, int]
    ) -> AsyncIterator[ToolStartStep | ToolResult]:
        """Execute a tool and yield progress updates for sub-agents.

        For tools with sub-agents, this yields ToolStartStep updates
        with sub_agent_progress. Always yields the final ToolResult.
        """
        # Cautious persona: gate write operations behind user confirmation
        agent_ctx = get_context()
        blocked_result = await self._check_cautious_write_gate(tool_call, agent_ctx)
        if blocked_result is not None:
            yield blocked_result
            return

        progress_queue: queue.Queue[SubAgentProgress] = queue.Queue()
        token_queue: queue.Queue[SubAgentTokenUsage] = queue.Queue()

        def progress_callback(progress: SubAgentProgress) -> None:
            progress_queue.put(progress)

        def token_callback(usage: SubAgentTokenUsage) -> None:
            token_queue.put(usage)

        logger.info("Tool call: %s(%s)", tool_call.name, tool_call.arguments)

        try:
            if tool_call.name in get_internal_tool_names():
                logger.info(f"Calling internal tool {tool_call.name}")
                # Create a per-tool AgentContext copy with isolated callbacks
                # to avoid races when multiple tools run in parallel
                agent_ctx = get_context()
                tool_ctx = dataclasses.replace(
                    agent_ctx,
                    progress_callback=progress_callback,
                    token_callback=token_callback,
                )

                def _run_internal_tool(tool_ctx: AgentContext, name: str, arguments: dict) -> object:
                    set_context(tool_ctx)
                    return execute_internal_tool(name, arguments)

                loop = asyncio.get_running_loop()
                ctx = copy_context()
                future = loop.run_in_executor(
                    None, partial(ctx.run, _run_internal_tool, tool_ctx, tool_call.name, tool_call.arguments)
                )

                while not future.done():
                    try:
                        progress = progress_queue.get_nowait()
                        yield ToolStartStep(
                            step_number=step_num,
                            tool_calls=tool_calls,
                            tool_progress=tool_progress,
                            current_tool=tool_call.name,
                            current_tool_call_id=tool_call.id,
                            sub_agent_progress=progress,
                        )
                    except queue.Empty:
                        pass

                    self._drain_token_queue(token_queue)
                    await asyncio.sleep(0.1)

                self._drain_token_queue(token_queue)

                result = future.result()
                content = str(result)
                logger.info(f"Internal tool {tool_call.name} result: {content}")
            else:
                result = await self.mcp_connection.call_tool(tool_call.name, tool_call.arguments)
                content = self._serialize_tool_result(result)

            content = maybe_spill(content, tool_call.name, step_num, get_context().get_output_dir(), tool_call.id)
            content = truncate_content(content)
            yield ToolResult(tool_call_id=tool_call.id, name=tool_call.name, content=content)

        except Exception as e:
            error_msg = f"Tool {tool_call.name} failed: {e}"
            logger.warning(f"Tool {tool_call.name} failed: {e}", exc_info=True)
            yield ToolResult(tool_call_id=tool_call.id, name=tool_call.name, content=error_msg, is_error=True)

    def _extract_text_from_prompt(self, prompt: UserContent) -> str:
        """Extract text content from a user prompt for classification."""
        if isinstance(prompt, str):
            return prompt
        text_parts: list[str] = []
        for block in prompt:
            if block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str):
                    text_parts.append(text)
        return " ".join(text_parts)

    def _calculate_rate_limit_delay(self, retries: int) -> float:
        """Calculate exponential backoff delay with jitter for rate limiting."""
        delay = min(RATE_LIMIT_BASE_DELAY * (2 ** (retries - 1)), RATE_LIMIT_MAX_DELAY)
        jitter = random.uniform(0, delay * 0.1)
        return delay + jitter

    async def run(self, prompt: UserContent) -> AsyncIterator[AgentStep]:
        """Run the agent with the given prompt, yielding steps.

        This method implements the main agent loop, calling the model,
        executing tools, and continuing until the model produces a final
        answer or the maximum number of steps is reached.

        Rate limiting is handled with exponential backoff and jitter.
        """
        loop = asyncio.get_running_loop()
        agent_ctx = get_context()
        agent_ctx.mcp_connection = self.mcp_connection
        agent_ctx.mcp_event_loop = loop

        # Pre-load tool categories based on keywords in the user's request
        # Run in thread pool to avoid blocking the event loop (preload uses sync MCP calls)
        request_text = self._extract_text_from_prompt(prompt)
        ctx = copy_context()
        preload_result = await loop.run_in_executor(
            None, partial(ctx.run, preload_categories_for_request, request_text)
        )

        self.memory.add_task(prompt, preload_info=preload_result)

        for step_num in range(1, self.config.max_steps + 1):
            rate_limit_retries = 0

            # Throttle requests to avoid rate limiting (skip delay on first step)
            if step_num > 1:
                await asyncio.sleep(self.config.request_delay)

            while True:
                try:
                    is_done = False
                    async for step in self._stream_model_response(step_num):
                        yield step
                        if isinstance(step, (FinalAnswerStep, ErrorStep)):
                            is_done = True

                    if is_done:
                        return

                    break

                except asyncio.CancelledError:
                    raise

                except RateLimitError as e:
                    rate_limit_retries += 1
                    if rate_limit_retries > RATE_LIMIT_MAX_RETRIES:
                        logger.error(f"Rate limit retries exhausted at step {step_num}: {e}")
                        yield ErrorStep(
                            step_number=step_num,
                            error=f"Rate limit exceeded after {RATE_LIMIT_MAX_RETRIES} retries. Please try again later.",
                        )
                        return

                    wait_time = self._calculate_rate_limit_delay(rate_limit_retries)
                    logger.warning(
                        f"Rate limit hit at step {step_num} (attempt {rate_limit_retries}/{RATE_LIMIT_MAX_RETRIES}), "
                        f"retrying in {wait_time:.1f}s: {e}"
                    )
                    yield ThinkingStep(
                        step_number=step_num,
                        thinking=f"⏳ Rate limited, waiting {wait_time:.1f}s before retry ({rate_limit_retries}/{RATE_LIMIT_MAX_RETRIES})...",
                    )
                    await asyncio.sleep(wait_time)

                except APIError as e:
                    is_timeout = isinstance(e, APITimeoutError)
                    log_fn = logger.warning if is_timeout else logger.error
                    log_fn(f"API {'timeout' if is_timeout else 'error'} at step {step_num}: {e}")
                    error_msg = (
                        f"Request timed out. Please try again. Details: {e}"
                        if is_timeout
                        else f"API error occurred: {e}"
                    )
                    yield ErrorStep(
                        step_number=step_num,
                        error=error_msg,
                    )
                    return

        else:
            yield ErrorStep(
                step_number=self.config.max_steps,
                error=f"Maximum steps ({self.config.max_steps}) reached without final answer.",
            )


async def create_agent(
    mcp_connection: MCPConnection,
    system_prompt: str,
    config: AgentConfig | None = None,
    additional_tools: list[ToolParam] | None = None,
) -> RossumAgent:
    """Create and configure a RossumAgent instance.

    This is a convenience factory function that creates the Bedrock client
    and initializes the agent with the provided configuration.
    """
    client = create_async_bedrock_client()
    return RossumAgent(
        client=client,
        mcp_connection=mcp_connection,
        system_prompt=system_prompt,
        config=config,
        additional_tools=additional_tools,
    )
