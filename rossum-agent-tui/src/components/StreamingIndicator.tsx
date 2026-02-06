import React from "react";
import { Text, Box } from "ink";
import { Spinner } from "@inkjs/ui";
import { getDisplayToolName } from "../utils/format.js";
import type { StepEvent, SubAgentProgressEvent } from "../types.js";

interface StreamingIndicatorProps {
  streaming: StepEvent;
  subAgentProgress: SubAgentProgressEvent | null;
}

export function StreamingIndicator({
  streaming,
  subAgentProgress,
}: StreamingIndicatorProps) {
  if (streaming.type === "final_answer" && streaming.content) {
    return (
      <Box flexDirection="column">
        <Text wrap="wrap">
          <Text color="green" bold>
            {"● "}
          </Text>
          {streaming.content}
        </Text>
        <Spinner label=" Writing..." />
      </Box>
    );
  }

  if (streaming.type === "tool_start" && streaming.tool_name) {
    const displayName = getDisplayToolName(
      streaming.tool_name,
      streaming.tool_arguments,
    );
    const progress = streaming.tool_progress
      ? ` (${streaming.tool_progress[0]}/${streaming.tool_progress[1]})`
      : "";

    return (
      <Box flexDirection="column">
        <Spinner label={` Running: ${displayName}${progress}`} />
        {subAgentProgress && (
          <Text color="blue" dimColor>
            {"    "}Sub-agent ({subAgentProgress.tool_name}): iteration{" "}
            {subAgentProgress.iteration}/{subAgentProgress.max_iterations},{" "}
            {subAgentProgress.status}
            {subAgentProgress.current_tool
              ? ` [${subAgentProgress.current_tool}]`
              : ""}
          </Text>
        )}
      </Box>
    );
  }

  if (streaming.type === "thinking") {
    const preview = streaming.content
      ? streaming.content.split("\n").slice(-3).join("\n")
      : "";
    return (
      <Box flexDirection="column">
        <Spinner label=" Thinking..." />
        {preview && (
          <Box marginLeft={2}>
            <Text dimColor italic wrap="wrap">
              {preview}
            </Text>
          </Box>
        )}
      </Box>
    );
  }

  if (streaming.type === "intermediate" && streaming.content) {
    return (
      <Box flexDirection="column">
        <Text wrap="wrap" dimColor>
          {"  "}
          {streaming.content}
        </Text>
        <Spinner label=" Processing..." />
      </Box>
    );
  }

  return <Spinner label=" Processing..." />;
}
