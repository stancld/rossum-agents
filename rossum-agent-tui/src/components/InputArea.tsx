import React from "react";
import { Box, Text } from "ink";
import { MultiLineInput } from "./MultiLineInput.js";
import type { ConnectionStatus, InteractionMode } from "../types.js";

interface InputAreaProps {
  onSubmit: (message: string) => void;
  connectionStatus: ConnectionStatus;
  mode: InteractionMode;
}

export function InputArea({
  onSubmit,
  connectionStatus,
  mode,
}: InputAreaProps) {
  const isDisabled =
    connectionStatus === "connecting" || connectionStatus === "streaming";

  if (mode === "browse") {
    return (
      <Box>
        <Text dimColor>{"  "}Press i or Tab to type a message</Text>
      </Box>
    );
  }

  return (
    <Box>
      <Text color={isDisabled ? "gray" : "green"} bold>
        {"❯ "}
      </Text>
      {isDisabled ? (
        <Text dimColor>Waiting for response...</Text>
      ) : (
        <MultiLineInput
          isActive={!isDisabled}
          placeholder="Type a message..."
          onSubmit={onSubmit}
        />
      )}
    </Box>
  );
}
