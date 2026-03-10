import React from "react";
import { Box, Text } from "ink";
import type { QuestionOption } from "../types.js";

/**
 * Render text with diff-aware colorization.
 *
 * Lines inside ```diff fences get per-line coloring:
 *   - lines starting with `-` → red
 *   - lines starting with `+` → green
 *   - lines starting with `@@` → cyan
 *   - other lines → dimmed (context)
 * Everything outside diff fences renders in the base color.
 */
function DiffAwareText({
  text,
  baseColor,
  bold,
}: {
  text: string;
  baseColor: string;
  bold: boolean;
}) {
  const diffBlockRe = /```diff\n([\s\S]*?)```/g;
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = diffBlockRe.exec(text)) !== null) {
    // Text before this diff block
    if (match.index > lastIndex) {
      parts.push(
        <Text key={`t${lastIndex}`} color={baseColor} bold={bold} wrap="wrap">
          {text.slice(lastIndex, match.index)}
        </Text>,
      );
    }

    // Diff block lines
    const diffContent = match[1]!;
    const lines = diffContent.split("\n");
    parts.push(
      <Box key={`d${match.index}`} flexDirection="column">
        {lines.map((line, i) => {
          let color: string;
          if (line.startsWith("+")) {
            color = "green";
          } else if (line.startsWith("-")) {
            color = "red";
          } else if (line.startsWith("@@")) {
            color = "cyan";
          } else {
            color = "gray";
          }
          return (
            <Text key={i} color={color}>
              {line}
            </Text>
          );
        })}
      </Box>,
    );

    lastIndex = match.index + match[0].length;
  }

  // Remaining text after last diff block (or all text if no diff blocks)
  if (lastIndex < text.length) {
    parts.push(
      <Text key={`t${lastIndex}`} color={baseColor} bold={bold} wrap="wrap">
        {text.slice(lastIndex)}
      </Text>,
    );
  }

  return <>{parts}</>;
}

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
      <DiffAwareText text={`? ${counter}${question}`} baseColor="yellow" bold />
      {options.length === 0 && (
        <Text dimColor italic>
          Type your answer below.
        </Text>
      )}
    </Box>
  );
}
