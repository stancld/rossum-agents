import type { ChatItem, ChatState, CompletedStep } from "../types.js";

function pairSteps(
  steps: CompletedStep[],
): Array<{ step: CompletedStep; resultStep?: CompletedStep }> {
  const resultsByCallId = new Map<string, CompletedStep>();
  const resultsByStep = new Map<number, CompletedStep>();
  for (const step of steps) {
    if (step.type === "tool_result") {
      if (step.toolCallId) {
        resultsByCallId.set(step.toolCallId, step);
      } else {
        resultsByStep.set(step.stepNumber, step);
      }
    }
  }

  const pairs: Array<{ step: CompletedStep; resultStep?: CompletedStep }> = [];
  for (const step of steps) {
    if (step.type === "tool_result") continue;
    if (step.type === "tool_start") {
      const result = step.toolCallId
        ? resultsByCallId.get(step.toolCallId)
        : resultsByStep.get(step.stepNumber);
      pairs.push({ step, resultStep: result });
    } else {
      pairs.push({ step });
    }
  }
  return pairs;
}

function pairedStepToItem(pair: {
  step: CompletedStep;
  resultStep?: CompletedStep;
}): ChatItem {
  const { step, resultStep } = pair;
  switch (step.type) {
    case "thinking":
      return {
        kind: "thinking",
        stepNumber: step.stepNumber,
        content: step.content || "",
      };
    case "tool_start":
      return {
        kind: "tool_call",
        stepNumber: step.stepNumber,
        step,
        resultStep,
      };
    case "intermediate":
      return {
        kind: "intermediate",
        stepNumber: step.stepNumber,
        content: step.content || "",
      };
    case "final_answer":
      return { kind: "final_answer", content: step.content || "" };
    case "error":
      return { kind: "error", content: step.content || "Unknown error" };
    default:
      return {
        kind: "intermediate",
        stepNumber: step.stepNumber,
        content: step.content || "",
      };
  }
}

export function buildChatItems(state: ChatState): ChatItem[] {
  const items: ChatItem[] = [];
  const paired = pairSteps(state.completedSteps);

  let msgIdx = 0;

  for (let i = 0; i < paired.length; i++) {
    while (
      msgIdx < state.userMessages.length &&
      state.userMessages[msgIdx]!.stepIndexBefore <=
        getOriginalStepIndex(paired, i)
    ) {
      items.push({
        kind: "user_message",
        text: state.userMessages[msgIdx]!.text,
      });
      msgIdx++;
    }
    items.push(pairedStepToItem(paired[i]!));
  }

  while (msgIdx < state.userMessages.length) {
    items.push({
      kind: "user_message",
      text: state.userMessages[msgIdx]!.text,
    });
    msgIdx++;
  }

  for (const f of state.files) {
    items.push({ kind: "file_created", filename: f.filename, url: f.url });
  }

  if (state.configCommit) {
    items.push({ kind: "config_commit", commit: state.configCommit });
  }

  if (
    state.error &&
    (paired.length === 0 || paired[paired.length - 1]?.step.type !== "error")
  ) {
    items.push({ kind: "error", content: state.error });
  }

  if (state.currentStreaming) {
    items.push({
      kind: "streaming",
      streaming: state.currentStreaming,
      subAgentProgress: state.subAgentProgress,
    });
  }

  return items;
}

function getOriginalStepIndex(
  paired: Array<{ step: CompletedStep; resultStep?: CompletedStep }>,
  pairIndex: number,
): number {
  // Count original steps consumed by pairs before this one
  let count = 0;
  for (let i = 0; i < pairIndex; i++) {
    count++;
    if (paired[i]!.resultStep) count++;
  }
  return count;
}
