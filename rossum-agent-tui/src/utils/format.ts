import type { JsonValue } from "../types.js";

export function getDisplayToolName(
  toolName: string,
  toolArguments: Record<string, JsonValue> | null,
): string {
  if (toolName === "call_on_connection" && toolArguments) {
    const connectionId = toolArguments["connection_id"];
    const innerTool = toolArguments["tool_name"];
    if (typeof connectionId === "string" && typeof innerTool === "string") {
      return `call_on_connection[${connectionId}.${innerTool}]`;
    }
  }
  return toolName;
}

export function truncate(text: string, maxLen = 120): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen) + "...";
}
