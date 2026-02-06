import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";
import type {
  ChatState,
  CompletedStep,
  UserMessage,
  TaskItem,
  FileCreatedEvent,
  TokenUsageBreakdown,
} from "../types.js";

const DIR = join(homedir(), ".rossum-agent-tui");
const FILE = join(DIR, "history.json");

interface PersistedState {
  chatId: string | null;
  completedSteps: CompletedStep[];
  userMessages: UserMessage[];
  tasks: TaskItem[];
  files: FileCreatedEvent[];
  tokenUsage: TokenUsageBreakdown | null;
  finalAnswer: string | null;
}

export function loadPersistedState(): ChatState | null {
  try {
    const data = readFileSync(FILE, "utf-8");
    const p = JSON.parse(data) as PersistedState;
    if (!p.chatId) return null;
    return {
      chatId: p.chatId,
      connectionStatus: "idle",
      completedSteps: p.completedSteps ?? [],
      currentStreaming: null,
      tasks: p.tasks ?? [],
      subAgentProgress: null,
      finalAnswer: p.finalAnswer ?? null,
      tokenUsage: p.tokenUsage ?? null,
      files: p.files ?? [],
      error: null,
      userMessages: p.userMessages ?? [],
    };
  } catch {
    return null;
  }
}

export function savePersistedState(state: ChatState): void {
  try {
    mkdirSync(DIR, { recursive: true });
    const p: PersistedState = {
      chatId: state.chatId,
      completedSteps: state.completedSteps,
      userMessages: state.userMessages,
      tasks: state.tasks,
      files: state.files,
      tokenUsage: state.tokenUsage,
      finalAnswer: state.finalAnswer,
    };
    writeFileSync(FILE, JSON.stringify(p));
  } catch {
    // Non-critical: TUI works without persistence
  }
}
