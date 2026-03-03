import React, { useState, useEffect } from "react";
import { Box, Text, useInput } from "ink";
import type { InteractionMode, QuestionOption } from "../types.js";

interface QuestionSelectorProps {
  options: QuestionOption[];
  multiSelect: boolean;
  onSubmit: (answer: string) => void;
  onOtherSelected: () => void;
  mode: InteractionMode;
  onHeightChange?: (rows: number) => void;
}

export function QuestionSelector({
  options,
  multiSelect,
  onSubmit,
  onOtherSelected,
  mode,
  onHeightChange,
}: QuestionSelectorProps) {
  const otherIndex = options.length;
  const totalItems = options.length + 1; // +1 for "Other"
  const [focusedIndex, setFocusedIndex] = useState(0);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const isActive = mode === "input";

  const totalRows = mode === "browse" ? 1 : totalItems + 1;
  useEffect(() => {
    onHeightChange?.(totalRows);
  }, [totalRows, onHeightChange]);

  useInput(
    (input, key) => {
      if (key.upArrow) {
        setFocusedIndex((prev) => Math.max(prev - 1, 0));
        return;
      }
      if (key.downArrow) {
        setFocusedIndex((prev) => Math.min(prev + 1, totalItems - 1));
        return;
      }
      if (multiSelect && input === " ") {
        if (focusedIndex === otherIndex) {
          onOtherSelected();
          return;
        }
        setSelected((prev) => {
          const next = new Set(prev);
          if (next.has(focusedIndex)) {
            next.delete(focusedIndex);
          } else {
            next.add(focusedIndex);
          }
          return next;
        });
        return;
      }
      if (key.return) {
        if (focusedIndex === otherIndex) {
          onOtherSelected();
          return;
        }
        if (multiSelect) {
          const labels = options
            .filter((_, i) => selected.has(i))
            .map((opt) => opt.label);
          if (labels.length > 0) {
            onSubmit(labels.join(", "));
          }
        } else {
          const opt = options[focusedIndex];
          if (opt) {
            onSubmit(opt.label);
          }
        }
      }
    },
    { isActive },
  );

  if (mode === "browse") {
    return (
      <Box>
        <Text dimColor>{"  "}Press i or Tab to answer</Text>
      </Box>
    );
  }

  const otherFocused = focusedIndex === otherIndex;

  return (
    <Box flexDirection="column">
      {options.map((opt, i) => {
        const isFocused = i === focusedIndex;
        const isChecked = selected.has(i);
        const pointer = isFocused ? "❯" : " ";
        const checkbox = multiSelect ? (isChecked ? " ◉" : " ○") : "";

        return (
          <Box key={opt.value}>
            <Text color={isFocused ? "cyan" : undefined} bold={isFocused}>
              {pointer}
              {checkbox} {opt.label}
            </Text>
            {opt.description ? <Text dimColor> {opt.description}</Text> : null}
          </Box>
        );
      })}
      <Box>
        <Text color={otherFocused ? "cyan" : undefined} bold={otherFocused}>
          {otherFocused ? "❯" : " "} Other (type your own)
        </Text>
      </Box>
      <Text dimColor>
        {"  "}
        {multiSelect
          ? "↑↓ navigate · Space toggle · Enter submit"
          : "↑↓ navigate · Enter select"}
      </Text>
    </Box>
  );
}
