import React from "react";
import { Box, Text } from "ink";
import { ThinkingBlock } from "./ThinkingBlock.js";
import { ToolCall } from "./ToolCall.js";
import { StreamingIndicator } from "./StreamingIndicator.js";
import { applyTerminalLinks } from "../utils/format.js";
import type { ChatItem, ConfigCommitInfo } from "../types.js";

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

function ConfigCommitItem({ commit }: { commit: ConfigCommitInfo }) {
  const suffix = commit.changesCount !== 1 ? "s" : "";
  return (
    <Text color="cyan">
      {"  ✓ "}
      <Text bold>Committed</Text> <Text dimColor>[{commit.hash}]</Text>{" "}
      {commit.message}{" "}
      <Text dimColor>
        ({commit.changesCount} change{suffix})
      </Text>
    </Text>
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
        <Box flexDirection="column">
          <Text color="green" bold wrap="wrap">
            {"❯ "}
            {item.text}
          </Text>
          {!!item.attachments?.length && (
            <Box paddingLeft={2} gap={1}>
              {item.attachments.map((att, i) => (
                <Text key={i} dimColor>
                  [{att.type === "image" ? "img" : "doc"}] {att.filename}
                </Text>
              ))}
            </Box>
          )}
        </Box>
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
          {applyTerminalLinks(item.content)}
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

    case "config_commit":
      return <ConfigCommitItem commit={item.commit} />;

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
