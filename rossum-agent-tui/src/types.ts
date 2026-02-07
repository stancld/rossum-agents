export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

export interface ChatResponse {
  chat_id: string;
  created_at: string;
}

export interface ChatSummary {
  chat_id: string;
  timestamp: number;
  message_count: number;
  first_message: string;
  preview: string | null;
}

export interface ChatListResponse {
  chats: ChatSummary[];
  total: number;
  limit: number;
  offset: number;
}

export type StepType =
  | "thinking"
  | "intermediate"
  | "tool_start"
  | "tool_result"
  | "final_answer"
  | "error";

export interface StepEvent {
  type: StepType;
  step_number: number;
  content: string | null;
  tool_name: string | null;
  tool_arguments: Record<string, JsonValue> | null;
  tool_progress: number[] | null; // [current, total] on the wire
  result: string | null;
  is_error: boolean;
  is_streaming: boolean;
  is_final: boolean;
  tool_call_id: string | null;
}

export type SubAgentStatus =
  | "thinking"
  | "searching"
  | "analyzing"
  | "reasoning"
  | "running_tool"
  | "completed"
  | "running";

export interface SubAgentProgressEvent {
  type: "sub_agent_progress";
  tool_name: string;
  iteration: number;
  max_iterations: number;
  current_tool: string | null;
  tool_calls: string[];
  status: SubAgentStatus;
}

export interface SubAgentTextEvent {
  type: "sub_agent_text";
  tool_name: string;
  text: string;
  is_final: boolean;
}

export interface TaskItem {
  id: string;
  subject: string;
  status: "pending" | "in_progress" | "completed";
  [key: string]: JsonValue;
}

export interface TaskSnapshotEvent {
  type: "task_snapshot";
  tasks: TaskItem[];
}

export interface TokenUsageBySource {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
}

export interface SubAgentTokenUsageDetail {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  by_tool: Record<string, TokenUsageBySource>;
}

export interface TokenUsageBreakdown {
  total: TokenUsageBySource;
  main_agent: TokenUsageBySource;
  sub_agents: SubAgentTokenUsageDetail;
}

export interface StreamDoneEvent {
  type: "done";
  total_steps: number;
  input_tokens: number;
  output_tokens: number;
  token_usage_breakdown: TokenUsageBreakdown | null;
}

export interface FileCreatedEvent {
  type: "file_created";
  filename: string;
  url: string;
}

export type SSEEvent =
  | { event: "step"; data: StepEvent }
  | { event: "sub_agent_progress"; data: SubAgentProgressEvent }
  | { event: "sub_agent_text"; data: SubAgentTextEvent }
  | { event: "task_snapshot"; data: TaskSnapshotEvent }
  | { event: "done"; data: StreamDoneEvent }
  | { event: "file_created"; data: FileCreatedEvent }
  | { event: "error"; data: { message: string } };

export type McpMode = "read-only" | "read-write";

export interface Config {
  apiUrl: string;
  token: string;
  rossumUrl: string;
  mcpMode: McpMode;
}

export type InteractionMode = "input" | "browse";

export type ChatItem =
  | { kind: "user_message"; text: string }
  | { kind: "thinking"; stepNumber: number; content: string }
  | {
      kind: "tool_call";
      stepNumber: number;
      step: CompletedStep;
      resultStep?: CompletedStep;
    }
  | { kind: "intermediate"; stepNumber: number; content: string }
  | { kind: "final_answer"; content: string }
  | { kind: "error"; content: string }
  | { kind: "file_created"; filename: string; url: string }
  | {
      kind: "streaming";
      streaming: StepEvent;
      subAgentProgress: SubAgentProgressEvent | null;
    };

export interface ExpandState {
  [itemIndex: number]: boolean;
}

export interface UserMessage {
  text: string;
  stepIndexBefore: number;
}

export type ConnectionStatus =
  | "disconnected"
  | "connecting"
  | "streaming"
  | "idle"
  | "error";

export interface CompletedStep {
  stepNumber: number;
  type: StepType;
  content: string | null;
  toolName: string | null;
  toolArguments: Record<string, JsonValue> | null;
  toolProgress: number[] | null;
  result: string | null;
  isError: boolean;
  toolCallId: string | null;
}

export interface ChatState {
  chatId: string | null;
  connectionStatus: ConnectionStatus;
  completedSteps: CompletedStep[];
  currentStreaming: StepEvent | null;
  tasks: TaskItem[];
  subAgentProgress: SubAgentProgressEvent | null;
  finalAnswer: string | null;
  tokenUsage: TokenUsageBreakdown | null;
  files: FileCreatedEvent[];
  error: string | null;
  userMessages: UserMessage[];
}
