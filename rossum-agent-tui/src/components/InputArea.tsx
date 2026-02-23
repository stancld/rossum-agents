import React, { useState, useCallback, useRef, useEffect } from "react";
import { Box, Text, useInput } from "ink";
import { CommandSuggest, getFilteredCommands } from "./CommandSuggest.js";
import { MultiLineInput, type MultiLineInputHandle } from "./MultiLineInput.js";
import type {
  CommandInfo,
  ConnectionStatus,
  InteractionMode,
} from "../types.js";

interface InputAreaProps {
  onSubmit: (message: string) => void;
  connectionStatus: ConnectionStatus;
  mode: InteractionMode;
  commands: CommandInfo[];
  onSuggestionRowsChange?: (rows: number) => void;
}

export function InputArea({
  onSubmit,
  connectionStatus,
  mode,
  commands,
  onSuggestionRowsChange,
}: InputAreaProps) {
  const [currentText, setCurrentText] = useState("");
  const [selectedSuggestion, setSelectedSuggestion] = useState(0);
  const inputRef = useRef<MultiLineInputHandle>(null);

  const isDisabled =
    connectionStatus === "connecting" || connectionStatus === "streaming";

  const isSingleLineSlash =
    !currentText.includes("\n") && currentText.trimStart().startsWith("/");
  const showSuggestions = mode === "input" && !isDisabled && isSingleLineSlash;

  const filtered = showSuggestions
    ? getFilteredCommands(commands, currentText.trimStart())
    : [];

  // Notify parent of suggestion row count changes for layout calculation
  const suggestionRows = showSuggestions ? Math.max(filtered.length, 1) : 0;
  useEffect(() => {
    onSuggestionRowsChange?.(suggestionRows);
  }, [suggestionRows, onSuggestionRowsChange]);

  const handleTextChange = useCallback((text: string) => {
    setCurrentText(text);
    setSelectedSuggestion(0);
  }, []);

  // Handle Tab and arrow keys for suggestion navigation
  useInput(
    (_input, key) => {
      if (key.tab && filtered.length > 0) {
        const selected = filtered[selectedSuggestion];
        if (selected) {
          inputRef.current?.setText(selected.name + " ");
        }
        return;
      }
      if (key.upArrow) {
        setSelectedSuggestion((prev) => Math.max(prev - 1, 0));
        return;
      }
      if (key.downArrow) {
        setSelectedSuggestion((prev) =>
          Math.min(prev + 1, filtered.length - 1),
        );
        return;
      }
    },
    { isActive: showSuggestions && filtered.length > 0 },
  );

  if (mode === "browse") {
    return (
      <Box>
        <Text dimColor>{"  "}Press i or Tab to type a message</Text>
      </Box>
    );
  }

  return (
    <Box flexDirection="column">
      <CommandSuggest
        commands={commands}
        filter={currentText.trimStart()}
        selectedIndex={selectedSuggestion}
        visible={showSuggestions}
      />
      <Box>
        <Text color={isDisabled ? "gray" : "green"} bold>
          {"❯ "}
        </Text>
        {isDisabled ? (
          <Text dimColor>Waiting for response...</Text>
        ) : (
          <MultiLineInput
            ref={inputRef}
            isActive={!isDisabled}
            placeholder="Type a message..."
            onSubmit={onSubmit}
            onChange={handleTextChange}
          />
        )}
      </Box>
    </Box>
  );
}
