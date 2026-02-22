import {
  useState,
  useEffect,
  useCallback,
  useImperativeHandle,
  useRef,
  forwardRef,
} from "react";
import { Box, Text, useInput, useStdin } from "ink";

interface MultiLineInputProps {
  onSubmit: (value: string) => void;
  isActive: boolean;
  placeholder?: string;
  onChange?: (text: string) => void;
}

export interface MultiLineInputHandle {
  setText: (text: string) => void;
}

export const MultiLineInput = forwardRef<
  MultiLineInputHandle,
  MultiLineInputProps
>(function MultiLineInput({ onSubmit, isActive, placeholder, onChange }, ref) {
  const [lines, setLines] = useState<string[]>([""]);
  const [cursorRow, setCursorRow] = useState(0);
  const [cursorCol, setCursorCol] = useState(0);
  const { stdin } = useStdin();

  // Notify parent when text changes via useEffect (React 18 batches setState
  // updaters, so capturing values from inside setLines is unreliable).
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  const text = lines.join("\n");
  useEffect(() => {
    onChangeRef.current?.(text);
  }, [text]);

  useImperativeHandle(
    ref,
    () => ({
      setText: (newText: string) => {
        const newLines = newText.split("\n");
        setLines(newLines);
        const lastRow = newLines.length - 1;
        setCursorRow(lastRow);
        setCursorCol(newLines[lastRow]!.length);
      },
    }),
    [],
  );

  const reset = useCallback(() => {
    setLines([""]);
    setCursorRow(0);
    setCursorCol(0);
  }, []);

  const handleMultiLinePaste = useCallback(
    (pastedLines: string[]) => {
      setLines((prev) => {
        const before = prev.slice(0, cursorRow);
        const currentLine = prev[cursorRow] ?? "";
        const leftOfCursor = currentLine.slice(0, cursorCol);
        const rightOfCursor = currentLine.slice(cursorCol);

        const merged: string[] = [...before];
        for (let i = 0; i < pastedLines.length; i++) {
          if (i === 0) {
            merged.push(leftOfCursor + pastedLines[i]!);
          } else if (i === pastedLines.length - 1) {
            merged.push(pastedLines[i]! + rightOfCursor);
          } else {
            merged.push(pastedLines[i]!);
          }
        }
        merged.push(...prev.slice(cursorRow + 1));

        const newRow = before.length + pastedLines.length - 1;
        const newCol = pastedLines[pastedLines.length - 1]!.length;
        setTimeout(() => {
          setCursorRow(newRow);
          setCursorCol(newCol);
        }, 0);

        return merged;
      });
    },
    [cursorRow, cursorCol],
  );

  const handleSingleLinePaste = useCallback(
    (str: string) => {
      setLines((prev) => {
        const updated = [...prev];
        const currentLine = updated[cursorRow] ?? "";
        updated[cursorRow] =
          currentLine.slice(0, cursorCol) + str + currentLine.slice(cursorCol);
        setTimeout(() => {
          setCursorCol(cursorCol + str.length);
        }, 0);
        return updated;
      });
    },
    [cursorRow, cursorCol],
  );

  // Multi-char paste bypasses useInput, so we handle it via raw stdin
  useEffect(() => {
    if (!isActive || !stdin) return;

    const onData = (data: Buffer) => {
      const str = data.toString("utf-8");

      // Ignore single-char inputs and control sequences — handled by useInput
      if (str.length <= 1 || str.startsWith("\x1b")) return;

      if (str.includes("\n") || str.includes("\r")) {
        handleMultiLinePaste(str.split(/\r\n|\r|\n/));
      } else {
        handleSingleLinePaste(str);
      }
    };

    stdin.on("data", onData);
    return () => {
      stdin.off("data", onData);
    };
  }, [isActive, stdin, handleMultiLinePaste, handleSingleLinePaste]);

  const handleSubmit = useCallback(() => {
    const trimmed = lines.join("\n").trim();
    if (!trimmed) return;
    onSubmit(trimmed);
    reset();
  }, [lines, onSubmit, reset]);

  const handleNewLine = useCallback(() => {
    setLines((prev) => {
      const currentLine = prev[cursorRow] ?? "";
      const before = currentLine.slice(0, cursorCol);
      const after = currentLine.slice(cursorCol);
      const updated = [...prev];
      updated.splice(cursorRow, 1, before, after);
      return updated;
    });
    setCursorRow((r) => r + 1);
    setCursorCol(0);
  }, [cursorRow, cursorCol]);

  const handleBackspace = useCallback(() => {
    if (cursorCol > 0) {
      setLines((prev) => {
        const updated = [...prev];
        const line = updated[cursorRow] ?? "";
        updated[cursorRow] =
          line.slice(0, cursorCol - 1) + line.slice(cursorCol);
        return updated;
      });
      setCursorCol((c) => c - 1);
    } else if (cursorRow > 0) {
      setLines((prev) => {
        const updated = [...prev];
        const prevLine = updated[cursorRow - 1] ?? "";
        const currentLine = updated[cursorRow] ?? "";
        const newCol = prevLine.length;
        updated.splice(cursorRow - 1, 2, prevLine + currentLine);
        setTimeout(() => setCursorCol(newCol), 0);
        return updated;
      });
      setCursorRow((r) => r - 1);
    }
  }, [cursorRow, cursorCol]);

  const handleArrowKeys = useCallback(
    (key: {
      leftArrow: boolean;
      rightArrow: boolean;
      upArrow: boolean;
      downArrow: boolean;
    }) => {
      if (key.leftArrow) {
        if (cursorCol > 0) {
          setCursorCol((c) => c - 1);
        } else if (cursorRow > 0) {
          const prevLineLen = (lines[cursorRow - 1] ?? "").length;
          setCursorRow((r) => r - 1);
          setCursorCol(prevLineLen);
        }
      } else if (key.rightArrow) {
        const lineLen = (lines[cursorRow] ?? "").length;
        if (cursorCol < lineLen) {
          setCursorCol((c) => c + 1);
        } else if (cursorRow < lines.length - 1) {
          setCursorRow((r) => r + 1);
          setCursorCol(0);
        }
      } else if (key.upArrow) {
        if (cursorRow > 0) {
          setCursorRow((r) => r - 1);
          const prevLineLen = (lines[cursorRow - 1] ?? "").length;
          setCursorCol(Math.min(cursorCol, prevLineLen));
        }
      } else if (key.downArrow) {
        if (cursorRow < lines.length - 1) {
          setCursorRow((r) => r + 1);
          const nextLineLen = (lines[cursorRow + 1] ?? "").length;
          setCursorCol(Math.min(cursorCol, nextLineLen));
        }
      }
    },
    [lines, cursorRow, cursorCol],
  );

  const handleCharInput = useCallback(
    (input: string) => {
      setLines((prev) => {
        const updated = [...prev];
        const line = updated[cursorRow] ?? "";
        updated[cursorRow] =
          line.slice(0, cursorCol) + input + line.slice(cursorCol);
        return updated;
      });
      setCursorCol((c) => c + 1);
    },
    [cursorRow, cursorCol],
  );

  useInput(
    (input, key) => {
      if (key.return && !key.shift) return handleSubmit();
      if (key.return && key.shift) return handleNewLine();
      if (key.backspace || key.delete) return handleBackspace();
      if (key.leftArrow || key.rightArrow || key.upArrow || key.downArrow)
        return handleArrowKeys(key);
      if (key.tab || key.ctrl || key.meta) return;
      if (input.length === 1) handleCharInput(input);
    },
    { isActive },
  );

  const isEmpty = lines.length === 1 && lines[0] === "";

  const MAX_VISIBLE_LINES = 10;
  const visibleCount = Math.min(lines.length, MAX_VISIBLE_LINES);
  const scrollOffset = Math.max(
    0,
    Math.min(
      cursorRow - MAX_VISIBLE_LINES + 1,
      lines.length - MAX_VISIBLE_LINES,
    ),
  );
  const visibleLines = lines.slice(scrollOffset, scrollOffset + visibleCount);

  return (
    <Box flexDirection="column">
      {isEmpty && placeholder ? (
        <Box>
          <Text dimColor>{placeholder}</Text>
          <Text backgroundColor="green"> </Text>
        </Box>
      ) : (
        visibleLines.map((line, visIdx) => {
          const rowIdx = scrollOffset + visIdx;
          const isCursorRow = rowIdx === cursorRow;
          if (!isCursorRow) {
            return (
              <Text key={rowIdx} wrap="truncate">
                {line}
              </Text>
            );
          }
          const before = line.slice(0, cursorCol);
          const cursorChar = line[cursorCol] ?? " ";
          const after = line.slice(cursorCol + 1);
          return (
            <Text key={rowIdx} wrap="truncate">
              {before}
              <Text backgroundColor="green" color="black">
                {cursorChar}
              </Text>
              {after}
            </Text>
          );
        })
      )}
      {lines.length > 1 && (
        <Text dimColor italic>
          ({lines.length} lines, showing {scrollOffset + 1}-
          {scrollOffset + visibleCount}) Shift+Enter: new line | Enter: send
        </Text>
      )}
    </Box>
  );
});
