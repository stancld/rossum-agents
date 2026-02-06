import React from "react";
import { Box, Text } from "ink";

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
  const arrow = expanded ? "▾" : "▸";

  if (!expanded) {
    return (
      <Text inverse={selected} dimColor italic>
        {arrow} Thought process
      </Text>
    );
  }

  return (
    <Box flexDirection="column">
      <Text inverse={selected} dimColor italic>
        {arrow} Thought process
      </Text>
      <Box marginLeft={2}>
        <Text dimColor wrap="wrap">
          {content}
        </Text>
      </Box>
    </Box>
  );
}
