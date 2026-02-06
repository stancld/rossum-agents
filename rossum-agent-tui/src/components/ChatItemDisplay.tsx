import React from "react";
import { Box, Text } from "ink";
import { ThinkingBlock } from "./ThinkingBlock.js";
import { ToolCall } from "./ToolCall.js";
import { StreamingIndicator } from "./StreamingIndicator.js";
import type { ChatItem } from "../types.js";

interface ChatItemDisplayProps {
  item: ChatItem;
  expanded: boolean;
  selected: boolean;
}

function IntermediateBlock({
  content,
  expanded,
  selected,
}: {
  content: string;
  expanded: boolean;
  selected: boolean;
}) {
  const lines = content.split("\n");
  const isLong = lines.length > 5;
  const arrow = expanded ? "▾" : "▸";

  if (!isLong) {
    return (
      <Text wrap="wrap" dimColor>
        {"  "}
        {content}
      </Text>
    );
  }

  if (!expanded) {
    const preview = lines.slice(0, 3).join("\n");
    return (
      <Text inverse={selected} dimColor>
        {arrow} {preview} ... ({lines.length} lines)
      </Text>
    );
  }

  return (
    <Box flexDirection="column">
      <Text inverse={selected} dimColor>
        {arrow} Content ({lines.length} lines)
      </Text>
      <Box marginLeft={2}>
        <Text dimColor wrap="wrap">
          {content}
        </Text>
      </Box>
    </Box>
  );
}

export const ChatItemDisplay = React.memo(function ChatItemDisplay({
  item,
  expanded,
  selected,
}: ChatItemDisplayProps) {
  switch (item.kind) {
    case "user_message":
      return (
        <Text color="green" bold wrap="wrap">
          {"❯ "}
          {item.text}
        </Text>
      );

    case "thinking":
      return (
        <ThinkingBlock
          content={item.content}
          expanded={expanded}
          selected={selected}
        />
      );

    case "tool_call":
      return (
        <ToolCall
          step={item.step}
          resultStep={item.resultStep}
          expanded={expanded}
          selected={selected}
        />
      );

    case "intermediate":
      return (
        <IntermediateBlock
          content={item.content}
          expanded={expanded}
          selected={selected}
        />
      );

    case "final_answer":
      return (
        <Text wrap="wrap">
          <Text color="green" bold>
            {"● "}
          </Text>
          {item.content}
        </Text>
      );

    case "error":
      return (
        <Text color="red" bold>
          Error: {item.content}
        </Text>
      );

    case "file_created":
      return (
        <Text color="blue">
          {"  📎 "}
          {item.filename} - {item.url}
        </Text>
      );

    case "streaming":
      return (
        <StreamingIndicator
          streaming={item.streaming}
          subAgentProgress={item.subAgentProgress}
        />
      );

    default:
      return null;
  }
});
