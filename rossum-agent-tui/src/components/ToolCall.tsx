import React from "react";
import { Box, Text } from "ink";
import { getDisplayToolName, truncate } from "../utils/format.js";
import type { CompletedStep, JsonValue } from "../types.js";

const RESULT_PREVIEW_LEN = 100;

function formatArgsSummary(args: Record<string, JsonValue> | null): string {
  if (!args) return "";
  const entries = Object.entries(args)
    .filter(([k]) => k !== "connection_id" && k !== "tool_name")
    .map(([k, v]) => `${k}=${typeof v === "string" ? v : JSON.stringify(v)}`)
    .join(", ");
  return entries ? truncate(entries, 80) : "";
}

function resultPreview(result: string): string {
  if (result.length <= RESULT_PREVIEW_LEN) return result.replace(/\n/g, " ");
  return result.slice(0, RESULT_PREVIEW_LEN).replace(/\n/g, " ") + "...";
}

interface ToolCallProps {
  step: CompletedStep;
  resultStep?: CompletedStep;
  expanded: boolean;
  selected: boolean;
}

export function ToolCall({
  step,
  resultStep,
  expanded,
  selected,
}: ToolCallProps) {
  const displayName = getDisplayToolName(
    step.toolName || "",
    step.toolArguments,
  );
  const progress = step.toolProgress
    ? ` [${step.toolProgress[0]}/${step.toolProgress[1]}]`
    : "";
  const arrow = expanded ? "▾" : "▸";
  const argsSummary = formatArgsSummary(step.toolArguments);
  const statusIcon = resultStep?.isError ? "✗" : "✓";
  const statusColor = resultStep?.isError ? "red" : "green";

  if (!expanded) {
    return (
      <Box flexDirection="column">
        <Text inverse={selected} color="cyan">
          {arrow} <Text color={statusColor}>{statusIcon}</Text> {displayName}
          {progress}
          {argsSummary ? ` (${argsSummary})` : ""}
        </Text>
        {resultStep?.result && (
          <Box marginLeft={4}>
            <Text dimColor italic>
              {resultPreview(resultStep.result)}
            </Text>
          </Box>
        )}
      </Box>
    );
  }

  return (
    <Box flexDirection="column">
      <Text inverse={selected} color="cyan">
        {arrow} <Text color={statusColor}>{statusIcon}</Text> {displayName}
        {progress}
      </Text>
      {step.toolArguments && Object.keys(step.toolArguments).length > 0 && (
        <Box marginLeft={2} flexDirection="column">
          {Object.entries(step.toolArguments)
            .filter(([k]) => k !== "connection_id" && k !== "tool_name")
            .map(([k, v]) => (
              <Text key={k} dimColor>
                {k}: {typeof v === "string" ? v : JSON.stringify(v)}
              </Text>
            ))}
        </Box>
      )}
      {resultStep?.result && (
        <Box marginLeft={2} flexDirection="column">
          <Text bold dimColor>
            Result:
          </Text>
          <Text color={resultStep.isError ? "red" : "gray"} wrap="wrap">
            {resultStep.result}
          </Text>
        </Box>
      )}
    </Box>
  );
}
