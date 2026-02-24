import React from "react";
import { Box, Text } from "ink";
import type { CommandInfo } from "../types.js";

interface CommandSuggestProps {
  commands: CommandInfo[];
  filter: string;
  selectedIndex: number;
  visible: boolean;
}

export function CommandSuggest({
  commands,
  filter,
  selectedIndex,
  visible,
}: CommandSuggestProps) {
  if (!visible) {
    return <Box height={0} />;
  }

  const filtered = getFilteredCommands(commands, filter);

  if (filtered.length === 0) {
    return (
      <Box paddingLeft={2}>
        <Text dimColor italic>
          No matching commands
        </Text>
      </Box>
    );
  }

  return (
    <Box flexDirection="column" paddingLeft={2}>
      {filtered.map((cmd, i) => {
        const isSelected = i === selectedIndex;
        return (
          <Box key={cmd.name}>
            <Text
              color={isSelected ? "black" : "cyan"}
              backgroundColor={isSelected ? "cyan" : undefined}
              bold={isSelected}
            >
              {cmd.name}
            </Text>
            <Text dimColor> {cmd.description}</Text>
          </Box>
        );
      })}
    </Box>
  );
}

export function getFilteredCommands(
  commands: CommandInfo[],
  filter: string,
): CommandInfo[] {
  return commands.filter((cmd) => cmd.name.startsWith(filter.toLowerCase()));
}
