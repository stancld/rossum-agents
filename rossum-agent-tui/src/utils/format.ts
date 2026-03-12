export function getDisplayToolName(
  toolName: string,
  toolArguments: Record<string, unknown> | null,
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

/** Build the collapsed one-liner for a thinking block. */
export function thinkingPreviewLine(content: string): string {
  const lines = content.split("\n");
  const lineCount = lines.length;
  const preview = truncate(
    lines
      .map((line) => line.trim())
      .filter((line) => line.length > 0)
      .slice(0, 2)
      .join(" "),
    100,
  );
  const previewSuffix = preview ? `: ${preview}` : "";
  const lineCountLabel = lineCount > 1 ? ` (${lineCount} lines)` : "";
  return `▸ Thought process${previewSuffix}${lineCountLabel}`;
}
