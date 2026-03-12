import React from "react";
import { Box, Text } from "ink";
import { thinkingPreviewLine } from "../utils/format.js";

interface ThinkingBlockProps {
  content: string;
  expanded: boolean;
  selected: boolean;
}

export function ThinkingBlock({
  content,
  expanded,
  selected,
}: ThinkingBlockProps) {
  if (!expanded) {
    return (
      <Text inverse={selected} dimColor italic>
        {thinkingPreviewLine(content)}
      </Text>
    );
  }

  const lines = content.split("\n");
  const lineCount = lines.length;
  const lineCountLabel = lineCount > 1 ? ` (${lineCount} lines)` : "";

  return (
    <Box flexDirection="column">
      <Text inverse={selected} dimColor italic>
        {"▾"} Thought process{lineCountLabel}
      </Text>
      <Box marginLeft={2}>
        <Text dimColor italic wrap="wrap">
          {content}
        </Text>
      </Box>
    </Box>
  );
}
