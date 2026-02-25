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
  onHeightChange?: (rows: number) => void;
}

function getSuggestionRows(visible: boolean, count: number): number {
  if (!visible) return 0;
  return Math.max(count, 1);
}

function getFileSuggestionRows(visible: boolean, entryCount: number): number {
  if (!visible) return 0;
  return Math.max(Math.min(entryCount, 8), 1) + (entryCount > 8 ? 1 : 0);
}

function computeInputAreaHeight(
  mode: InteractionMode,
  isDisabled: boolean,
  suggestionRows: number,
  currentText: string,
): number {
  if (mode === "browse") return 1;
  const inputLineCount = currentText ? currentText.split("\n").length : 1;
  const visibleInputRows = Math.min(inputLineCount, 10);
  const inputFooterRows = inputLineCount > 1 ? 1 : 0;
  const mainInputRows = isDisabled ? 1 : visibleInputRows + inputFooterRows;
  return suggestionRows + mainInputRows;
}

interface CommandSuggestionState {
  show: boolean;
  filtered: CommandInfo[];
  matchedCommand: CommandInfo | undefined;
  trimmedText: string;
}

function getCommandSuggestionState(
  commands: CommandInfo[],
  currentText: string,
  canSuggest: boolean,
): CommandSuggestionState {
  const isSingleLineSlash =
    !currentText.includes("\n") && currentText.trimStart().startsWith("/");
  const show = canSuggest && isSingleLineSlash;

  if (!show) {
    return {
      show: false,
      filtered: [],
      matchedCommand: undefined,
      trimmedText: "",
    };
  }

  const trimmedText = currentText.trimStart();
  const spaceIdx = trimmedText.indexOf(" ");
  const matchedCommand =
    spaceIdx !== -1
      ? commands.find(
          (c) =>
            c.name === trimmedText.slice(0, spaceIdx) &&
            (c.argument_suggestions?.length ?? 0) > 0,
        )
      : undefined;

  if (matchedCommand) {
    const argPartial = trimmedText.slice(spaceIdx + 1).toLowerCase();
    const filtered = (matchedCommand.argument_suggestions ?? [])
      .filter((s) => s.value.startsWith(argPartial))
      .map((s) => ({ name: s.value, description: s.description }));
    return { show: true, filtered, matchedCommand, trimmedText };
  }

  return {
    show: true,
    filtered: getFilteredCommands(commands, trimmedText),
    matchedCommand: undefined,
    trimmedText,
  };
}

export function InputArea({
  onSubmit,
  connectionStatus,
  mode,
  commands,
  onHeightChange,
}: InputAreaProps) {
  const [currentText, setCurrentText] = useState("");
  const [selectedSuggestion, setSelectedSuggestion] = useState(0);
  const [cursorRow, setCursorRow] = useState(0);
  const [cursorCol, setCursorCol] = useState(0);
  const inputRef = useRef<MultiLineInputHandle>(null);

  const isDisabled =
    connectionStatus === "connecting" || connectionStatus === "streaming";
  const canSuggest = mode === "input" && !isDisabled;

  // Command / argument suggestions (/ prefix)
  const cmdState = getCommandSuggestionState(commands, currentText, canSuggest);
  const showCommandSuggestions = cmdState.show;
  const filteredCommands = cmdState.filtered;

  // File suggestions (@ prefix with path)
  const fileSuggest = useFileSuggest(currentText, cursorRow, cursorCol);
  const showFileSuggestions =
    canSuggest && !showCommandSuggestions && fileSuggest.visible;

  // Notify parent of total rendered height for layout calculation
  const suggestionRows =
    getSuggestionRows(showCommandSuggestions, filteredCommands.length) +
    getFileSuggestionRows(showFileSuggestions, fileSuggest.entries.length);
  const totalRows = computeInputAreaHeight(
    mode,
    isDisabled,
    suggestionRows,
    currentText,
  );

  useEffect(() => {
    onHeightChange?.(totalRows);
  }, [totalRows, onHeightChange]);

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
          if (cmdState.matchedCommand) {
            inputRef.current?.setText(
              cmdState.matchedCommand.name + " " + selected.name,
            );
          } else {
            inputRef.current?.setText(selected.name + " ");
          }
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
    { isActive: filteredCommands.length > 0 },
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
    { isActive: showFileSuggestions },
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
        commands={cmdState.matchedCommand ? filteredCommands : commands}
        filter={cmdState.matchedCommand ? "" : cmdState.trimmedText}
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
          <Text dimColor>Waiting for response... (Ctrl+X to stop)</Text>
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
