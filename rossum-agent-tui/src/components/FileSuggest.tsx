import React from "react";
import { Box, Text } from "ink";
import type { FileEntry } from "../utils/fileAttachments.js";

interface FileSuggestProps {
  entries: FileEntry[];
  selectedIndex: number;
  visible: boolean;
  loading: boolean;
}

const MAX_VISIBLE = 8;

export function FileSuggest({
  entries,
  selectedIndex,
  visible,
  loading,
}: FileSuggestProps) {
  if (!visible) {
    return <Box height={0} />;
  }

  if (loading && entries.length === 0) {
    return (
      <Box paddingLeft={2}>
        <Text dimColor italic>
          Loading...
        </Text>
      </Box>
    );
  }

  if (entries.length === 0) {
    return (
      <Box paddingLeft={2}>
        <Text dimColor italic>
          No matching files
        </Text>
      </Box>
    );
  }

  // Window around selected index
  const half = Math.floor(MAX_VISIBLE / 2);
  let start = Math.max(0, selectedIndex - half);
  const end = Math.min(entries.length, start + MAX_VISIBLE);
  if (end - start < MAX_VISIBLE) {
    start = Math.max(0, end - MAX_VISIBLE);
  }
  const visibleEntries = entries.slice(start, end);

  return (
    <Box flexDirection="column" paddingLeft={2}>
      {visibleEntries.map((entry, i) => {
        const realIndex = start + i;
        const isSelected = realIndex === selectedIndex;
        const displayName = entry.isDirectory ? entry.name + "/" : entry.name;
        return (
          <Box key={entry.name}>
            <Text
              color={
                isSelected ? "black" : entry.isDirectory ? "cyan" : "white"
              }
              backgroundColor={isSelected ? "cyan" : undefined}
              bold={isSelected}
            >
              {displayName}
            </Text>
          </Box>
        );
      })}
      {entries.length > MAX_VISIBLE && (
        <Text dimColor italic>
          {" "}
          ({entries.length} items)
        </Text>
      )}
    </Box>
  );
}
