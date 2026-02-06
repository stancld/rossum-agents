import { useState, useCallback, useRef, useEffect } from "react";
import { createChat } from "../api/client.js";
import { streamMessage } from "../api/sse.js";
import {
  loadPersistedState,
  savePersistedState,
} from "../utils/persistence.js";
import type {
  ChatState,
  CompletedStep,
  Config,
  FileCreatedEvent,
  SSEEvent,
  StepEvent,
  SubAgentProgressEvent,
  TaskItem,
  TokenUsageBreakdown,
  UserMessage,
} from "../types.js";

const INITIAL_STATE: ChatState = {
  chatId: null,
  connectionStatus: "disconnected",
  completedSteps: [],
  currentStreaming: null,
  tasks: [],
  subAgentProgress: null,
  finalAnswer: null,
  tokenUsage: null,
  files: [],
  error: null,
  userMessages: [],
};

function stepToCompleted(step: StepEvent): CompletedStep {
  return {
    stepNumber: step.step_number,
    type: step.type,
    content: step.content,
    toolName: step.tool_name,
    toolArguments: step.tool_arguments,
    toolProgress: step.tool_progress,
    result: step.result,
    isError: step.is_error,
    toolCallId: step.tool_call_id,
  };
}

function isDifferentStep(a: StepEvent, b: StepEvent): boolean {
  return a.step_number !== b.step_number || a.type !== b.type;
}

function handleStepEvent(prev: ChatState, step: StepEvent): ChatState {
  if (step.type === "error") {
    return {
      ...prev,
      error: step.content || "Unknown error",
      connectionStatus: "error",
    };
  }

  if (step.is_streaming) {
    const finalAnswer =
      step.type === "final_answer"
        ? step.content || prev.finalAnswer
        : prev.finalAnswer;

    // If we're switching to a different step while the previous one was still
    // streaming, commit the previous streaming step to completedSteps so it
    // doesn't get lost (e.g. thinking block replaced by tool_start).
    const prevStream = prev.currentStreaming;
    if (prevStream && isDifferentStep(prevStream, step)) {
      return {
        ...prev,
        completedSteps: [...prev.completedSteps, stepToCompleted(prevStream)],
        currentStreaming: step,
        finalAnswer,
      };
    }
    return { ...prev, currentStreaming: step, finalAnswer };
  }

  const prevStream = prev.currentStreaming;
  const extraSteps: CompletedStep[] =
    prevStream && isDifferentStep(prevStream, step)
      ? [stepToCompleted(prevStream)]
      : [];

  return {
    ...prev,
    completedSteps: [
      ...prev.completedSteps,
      ...extraSteps,
      stepToCompleted(step),
    ],
    currentStreaming: null,
    finalAnswer:
      step.type === "final_answer" && step.is_final
        ? step.content || prev.finalAnswer
        : prev.finalAnswer,
  };
}

export function useChat(config: Config) {
  const [state, setState] = useState<ChatState>(
    () => loadPersistedState() ?? INITIAL_STATE,
  );
  const abortRef = useRef<AbortController | null>(null);
  const chatIdRef = useRef<string | null>(state.chatId);

  useEffect(() => {
    if (state.connectionStatus !== "streaming") {
      savePersistedState(state);
    }
  }, [state]);

  const dispatch = useCallback((event: SSEEvent) => {
    setState((prev) => {
      switch (event.event) {
        case "step":
          return handleStepEvent(prev, event.data);

        case "task_snapshot":
          return { ...prev, tasks: event.data.tasks as TaskItem[] };

        case "sub_agent_progress":
          return {
            ...prev,
            subAgentProgress: event.data as SubAgentProgressEvent,
          };

        case "sub_agent_text":
          return prev;

        case "done": {
          const lastStream = prev.currentStreaming;
          const extra: CompletedStep[] = lastStream
            ? [stepToCompleted(lastStream)]
            : [];
          return {
            ...prev,
            connectionStatus: "idle",
            completedSteps: [...prev.completedSteps, ...extra],
            currentStreaming: null,
            subAgentProgress: null,
            tokenUsage: event.data
              .token_usage_breakdown as TokenUsageBreakdown | null,
          };
        }

        case "file_created":
          return {
            ...prev,
            files: [...prev.files, event.data as FileCreatedEvent],
          };

        case "error":
          return {
            ...prev,
            error: (event.data as { message: string }).message,
            connectionStatus: "error",
          };

        default:
          return prev;
      }
    });
  }, []);

  const sendMessage = useCallback(
    async (message: string) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setState((prev) => ({
        ...prev,
        connectionStatus: "connecting",
        completedSteps: prev.chatId ? prev.completedSteps : [],
        currentStreaming: null,
        subAgentProgress: null,
        finalAnswer: null,
        tokenUsage: null,
        tasks: [],
        error: null,
        userMessages: [
          ...prev.userMessages,
          { text: message, stepIndexBefore: prev.completedSteps.length },
        ],
      }));

      try {
        let chatId = chatIdRef.current;
        if (!chatId) {
          const chat = await createChat(config);
          chatId = chat.chat_id;
          chatIdRef.current = chatId;
          setState((prev) => ({ ...prev, chatId }));
        }

        setState((prev) => ({ ...prev, connectionStatus: "streaming" }));

        await streamMessage({
          config,
          chatId,
          message,
          onEvent: dispatch,
          onError: (err) => {
            setState((prev) => ({
              ...prev,
              error: err.message,
              connectionStatus: "error",
            }));
          },
          onDone: () => {
            setState((prev) => ({
              ...prev,
              connectionStatus:
                prev.connectionStatus === "error" ? "error" : "idle",
            }));
          },
          signal: controller.signal,
        });
      } catch (err) {
        if (!controller.signal.aborted) {
          setState((prev) => ({
            ...prev,
            error: err instanceof Error ? err.message : String(err),
            connectionStatus: "error",
          }));
        }
      }
    },
    [config, dispatch],
  );

  const resetChat = useCallback(() => {
    abortRef.current?.abort();
    chatIdRef.current = null;
    setState(INITIAL_STATE);
  }, []);

  return { state, sendMessage, resetChat };
}
