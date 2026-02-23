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

// Replace [text](url) markdown links with OSC 8 terminal hyperlinks.
// Supported by iTerm2, WezTerm, modern gnome-terminal, etc.
// Falls back to plain text in unsupported terminals.
export function applyTerminalLinks(text: string): string {
  return text.replace(
    /\[([^\]]+)\]\(([^)]+)\)/g,
    (_match, linkText: string, url: string) =>
      `\x1B]8;;${url}\x07\x1B[1;34m${linkText}\x1B[0m\x1B]8;;\x07`,
  );
}
