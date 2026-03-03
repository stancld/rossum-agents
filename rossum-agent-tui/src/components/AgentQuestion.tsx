import React from "react";
import { Box, Text } from "ink";
import type { QuestionOption } from "../types.js";

interface AgentQuestionProps {
  question: string;
  options: QuestionOption[];
  multiSelect: boolean;
  questionIndex: number;
  totalQuestions: number;
}

export function AgentQuestion({
  question,
  options,
  questionIndex,
  totalQuestions,
}: AgentQuestionProps) {
  const counter =
    totalQuestions > 1 ? `[${questionIndex + 1}/${totalQuestions}] ` : "";

  return (
    <Box flexDirection="column" marginY={1}>
      <Text color="yellow" bold wrap="wrap">
        {"? "}
        {counter}
        {question}
      </Text>
      {options.length === 0 && (
        <Text dimColor italic>
          Type your answer below.
        </Text>
      )}
    </Box>
  );
}
