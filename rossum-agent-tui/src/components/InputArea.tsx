import React, { useState, useCallback, useRef, useEffect } from "react";
import { Box, Text, useInput } from "ink";
import { CommandSuggest, getFilteredCommands } from "./CommandSuggest.js";
import { FileSuggest } from "./FileSuggest.js";
import { MultiLineInput, type MultiLineInputHandle } from "./MultiLineInput.js";
import { useFileSuggest } from "../hooks/useFileSuggest.js";
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
  const [cursorRow, setCursorRow] = useState(0);
  const [cursorCol, setCursorCol] = useState(0);
  const inputRef = useRef<MultiLineInputHandle>(null);

  const isDisabled =
    connectionStatus === "connecting" || connectionStatus === "streaming";

  // Command suggestions (/ prefix)
  const isSingleLineSlash =
    !currentText.includes("\n") && currentText.trimStart().startsWith("/");
  const showCommandSuggestions =
    mode === "input" && !isDisabled && isSingleLineSlash;

  const filteredCommands = showCommandSuggestions
    ? getFilteredCommands(commands, currentText.trimStart())
    : [];

  // File suggestions (@ prefix with path)
  const fileSuggest = useFileSuggest(currentText, cursorRow, cursorCol);
  const showFileSuggestions =
    mode === "input" &&
    !isDisabled &&
    !showCommandSuggestions &&
    fileSuggest.visible;

  // Notify parent of suggestion row count changes for layout calculation
  const commandSuggestionRows = showCommandSuggestions
    ? Math.max(filteredCommands.length, 1)
    : 0;
  const fileSuggestionRows = showFileSuggestions
    ? Math.max(Math.min(fileSuggest.entries.length, 8), 1) +
      (fileSuggest.entries.length > 8 ? 1 : 0)
    : 0;
  const suggestionRows = commandSuggestionRows + fileSuggestionRows;

  useEffect(() => {
    onSuggestionRowsChange?.(suggestionRows);
  }, [suggestionRows, onSuggestionRowsChange]);

  const handleTextChange = useCallback((text: string) => {
    setCurrentText(text);
    setSelectedSuggestion(0);
  }, []);

  const handleCursorChange = useCallback((row: number, col: number) => {
    setCursorRow(row);
    setCursorCol(col);
  }, []);

  // Replace the @partial text at cursor with the completed path
  const completeFileSelection = useCallback(
    (entry: { name: string; isDirectory: boolean }) => {
      const partial = fileSuggest.partialPath;
      // Extract directory portion of partial
      let dirPath: string;
      if (partial === "" || partial.endsWith("/")) {
        dirPath = partial;
      } else {
        const lastSlash = partial.lastIndexOf("/");
        dirPath = lastSlash === -1 ? "" : partial.slice(0, lastSlash + 1);
      }

      let completedPath = dirPath + entry.name;
      // Prepend ./ for bare relative paths so parseAtTokens still matches
      if (!/^(~\/|\.\/|\.\.\/|\/)/.test(completedPath)) {
        completedPath = "./" + completedPath;
      }
      const suffix = entry.isDirectory ? "/" : " ";

      // Replace @partial with @completedPath in the text
      const lines = currentText.split("\n");
      const line = lines[cursorRow] ?? "";
      const before = line.slice(0, cursorCol);
      const atIdx = before.lastIndexOf("@" + partial);
      if (atIdx === -1) return;

      const newBefore = before.slice(0, atIdx) + "@" + completedPath + suffix;
      lines[cursorRow] = newBefore + line.slice(cursorCol);
      const newText = lines.join("\n");
      inputRef.current?.setText(newText);
    },
    [fileSuggest.partialPath, currentText, cursorRow, cursorCol],
  );

  // Handle Tab and arrow keys for command suggestion navigation
  useInput(
    (_input, key) => {
      if (key.tab && filteredCommands.length > 0) {
        const selected = filteredCommands[selectedSuggestion];
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
          Math.min(prev + 1, filteredCommands.length - 1),
        );
        return;
      }
    },
    { isActive: showCommandSuggestions && filteredCommands.length > 0 },
  );

  // Handle Tab and arrow keys for file suggestion navigation
  useInput(
    (_input, key) => {
      if (key.tab) {
        const entry = fileSuggest.getSelectedEntry();
        if (entry) {
          completeFileSelection(entry);
        }
        return;
      }
      if (key.upArrow) {
        fileSuggest.moveUp();
        return;
      }
      if (key.downArrow) {
        fileSuggest.moveDown();
        return;
      }
    },
    { isActive: showFileSuggestions && fileSuggest.entries.length > 0 },
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
        visible={showCommandSuggestions}
      />
      <FileSuggest
        entries={fileSuggest.entries}
        selectedIndex={fileSuggest.selectedIndex}
        visible={showFileSuggestions}
        loading={fileSuggest.loading}
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
            onCursorChange={handleCursorChange}
          />
        )}
      </Box>
    </Box>
  );
}
