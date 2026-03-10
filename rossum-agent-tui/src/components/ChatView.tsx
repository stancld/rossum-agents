import React, { useState, useEffect, useMemo, useRef } from "react";
import { Box, Text } from "ink";
import { ChatItemDisplay } from "./ChatItemDisplay.js";
import type { ChatItem, ExpandState } from "../types.js";
import stripAnsi from "strip-ansi";
import {
  getDisplayToolName,
  thinkingPreviewLine,
  truncate,
} from "../utils/format.js";
import { renderMarkdown } from "../utils/markdown.js";

interface ChatViewProps {
  items: ChatItem[];
  expandState: ExpandState;
  selectedIndex: number;
  height: number;
  width: number;
  browseMode: boolean;
  autoScrollToBottom: boolean;
  scrollNudge: number;
}

const ROSSUM_PATTERN = "ROSSUM";

function fillPatternSegment(
  grid: string[][],
  y: number,
  fromX: number,
  toX: number,
  seed: number,
): void {
  const width = grid[0]?.length ?? 0;
  let index = seed;

  for (let x = fromX; x <= toX; x++) {
    if (x < 0 || x >= width) {
      continue;
    }
    grid[y]![x] = ROSSUM_PATTERN[index % ROSSUM_PATTERN.length]!;
    index += 1;
  }
}

function buildRossumCircle(width: number, height: number): string[] {
  const maxCols = Math.max(width - 4, 0);
  const maxRows = Math.max(height - 2, 0);
  if (maxCols < 12 || maxRows < 6) {
    return [ROSSUM_PATTERN.repeat(2)];
  }

  const xScale = 2.2;
  const maxRadius = Math.max(
    4,
    Math.floor(Math.min((maxCols - 2) / (2 * xScale), (maxRows - 2) / 2)),
  );
  const outerRadius = Math.max(4, Math.floor(maxRadius * 0.78));
  const yStep = 0.9;
  const strokeWidth = Math.min(6, Math.max(4, Math.floor(outerRadius / 2.5)));
  const innerRadius = Math.max(1, outerRadius - strokeWidth + 1);
  let rows = Math.floor((2 * outerRadius) / yStep) + 1;
  if (rows % 2 === 0) {
    rows += 1;
  }
  let cols = Math.round(outerRadius * 2 * xScale) + 1;
  if (cols % 2 === 0) {
    cols += 1;
  }
  rows = Math.min(rows, maxRows);
  cols = Math.min(cols, maxCols);
  const centerX = (cols - 1) / 2;
  const centerY = (rows - 1) / 2;
  const grid = Array.from({ length: rows }, () => Array(cols).fill(" "));

  for (let y = 0; y < rows; y++) {
    const dy = (y - centerY) * yStep;
    const outerBand = outerRadius * outerRadius - dy * dy;
    if (outerBand < 0) {
      continue;
    }

    const outerX = Math.sqrt(outerBand) * xScale;
    const leftOuter = Math.round(centerX - outerX);
    const rightOuter = Math.round(centerX + outerX);

    const innerBand = innerRadius * innerRadius - dy * dy;
    if (innerBand <= 0) {
      fillPatternSegment(grid, y, leftOuter, rightOuter, y);
      continue;
    }

    const innerX = Math.sqrt(innerBand) * xScale;
    const leftInner = Math.round(centerX - innerX);
    const rightInner = Math.round(centerX + innerX);

    fillPatternSegment(grid, y, leftOuter, leftInner - 1, y);
    fillPatternSegment(grid, y, rightInner + 1, rightOuter, y + 3);
  }

  return grid.map((row) => row.join("").replace(/\s+$/, ""));
}

function countWrappedLines(text: string, width: number): number {
  const effectiveWidth = Math.max(1, width);
  const lines = text.split("\n");
  return lines.reduce(
    (sum, line) =>
      sum + Math.max(1, Math.ceil(stripAnsi(line).length / effectiveWidth)),
    0,
  );
}

interface Widths {
  content: number;
  indented: number;
  deepIndented: number;
}

function estimateToolCallHeight(
  item: Extract<ChatItem, { kind: "tool_call" }>,
  expanded: boolean,
  w: Widths,
): number {
  const displayName = getDisplayToolName(
    item.step.toolName || "",
    item.step.toolArguments,
  );
  const progress = item.step.toolProgress
    ? ` [${item.step.toolProgress[0]}/${item.step.toolProgress[1]}]`
    : "";

  if (!expanded) {
    const argsSummary = item.step.toolArguments
      ? truncate(
          Object.entries(item.step.toolArguments)
            .filter(([k]) => k !== "connection_id" && k !== "tool_name")
            .map(
              ([k, v]) =>
                `${k}=${typeof v === "string" ? v : JSON.stringify(v)}`,
            )
            .join(", "),
          80,
        )
      : "";
    const header = `▸ ${displayName}${progress}${argsSummary ? ` (${argsSummary})` : ""}`;
    const preview = item.resultStep?.result
      ? truncate(item.resultStep.result.replace(/\n/g, " "), 100)
      : "";
    return (
      countWrappedLines(header, w.content) +
      (preview ? countWrappedLines(preview, w.deepIndented) : 0)
    );
  }

  let h = countWrappedLines(`▾ ${displayName}${progress}`, w.content);
  if (item.step.toolArguments) {
    h += Object.entries(item.step.toolArguments)
      .filter(([k]) => k !== "connection_id" && k !== "tool_name")
      .reduce((sum, [k, v]) => {
        const value = typeof v === "string" ? v : JSON.stringify(v);
        return sum + countWrappedLines(`${k}: ${value}`, w.indented);
      }, 0);
  }
  if (item.resultStep?.result) {
    h += 1 + countWrappedLines(item.resultStep.result, w.indented);
  }
  return h;
}

function estimateStreamingToolStartHeight(
  item: Extract<ChatItem, { kind: "streaming" }>,
  w: Widths,
): number {
  const displayName = getDisplayToolName(
    item.streaming.tool_name!,
    item.streaming.tool_arguments,
  );
  const progress = item.streaming.tool_progress
    ? ` (${item.streaming.tool_progress[0]}/${item.streaming.tool_progress[1]})`
    : "";
  let h = countWrappedLines(`Running: ${displayName}${progress}`, w.content);
  if (item.subAgentProgress) {
    const p = item.subAgentProgress;
    const suffix = p.current_tool ? ` [${p.current_tool}]` : "";
    const line = `Sub-agent (${p.tool_name}): iteration ${p.iteration}/${p.max_iterations}, ${p.status}${suffix}`;
    h += countWrappedLines(line, w.content);
  }
  if (item.subAgentText?.text) {
    h += countWrappedLines(item.subAgentText.text, w.indented);
  }
  return h;
}

function estimateStreamingHeight(
  item: Extract<ChatItem, { kind: "streaming" }>,
  w: Widths,
): number {
  if (item.streaming.type === "final_answer" && item.streaming.content) {
    return countWrappedLines(`● ${item.streaming.content}`, w.content) + 1;
  }
  if (item.streaming.type === "tool_start" && item.streaming.tool_name) {
    return estimateStreamingToolStartHeight(item, w);
  }
  if (item.streaming.type === "thinking") {
    const preview = item.streaming.content
      ? item.streaming.content.split("\n").slice(-3).join("\n")
      : "";
    return 1 + (preview ? countWrappedLines(preview, w.indented) : 0);
  }
  if (item.streaming.type === "intermediate" && item.streaming.content) {
    return countWrappedLines(`  ${item.streaming.content}`, w.content) + 1;
  }
  return 1;
}

function estimateUserMessageHeight(
  item: Extract<ChatItem, { kind: "user_message" }>,
  w: Widths,
): number {
  const messageHeight = countWrappedLines(`❯ ${item.text}`, w.content);
  const attachmentsHeight =
    item.attachments && item.attachments.length > 0
      ? countWrappedLines(
          item.attachments
            .map(
              (att) =>
                `[${att.type === "image" ? "img" : "doc"}] ${att.filename}`,
            )
            .join(" "),
          w.indented,
        )
      : 0;
  return messageHeight + attachmentsHeight;
}

function estimateThinkingHeight(
  item: Extract<ChatItem, { kind: "thinking" }>,
  expanded: boolean,
  w: Widths,
): number {
  if (expanded) {
    return 1 + countWrappedLines(item.content, w.indented);
  }
  return countWrappedLines(thinkingPreviewLine(item.content), w.content);
}

function estimateIntermediateHeight(
  item: Extract<ChatItem, { kind: "intermediate" }>,
  expanded: boolean,
  w: Widths,
): number {
  const rawLines = item.content.split("\n");
  const lines = rawLines.length;
  if (!expanded) {
    const preview = truncate(
      rawLines
        .map((line) => line.trim())
        .filter((line) => line.length > 0)
        .slice(0, 2)
        .join(" "),
      100,
    );
    const suffix = lines > 1 ? ` ... (${lines} lines)` : "";
    return countWrappedLines(`▸ ${preview || "(empty)"}${suffix}`, w.content);
  }
  return 1 + countWrappedLines(item.content, w.indented);
}

function estimateFinalAnswerHeight(
  item: Extract<ChatItem, { kind: "final_answer" }>,
  expanded: boolean,
  w: Widths,
): number {
  const lines = item.content.split("\n");
  if (!expanded) {
    const firstLine = truncate(
      lines.map((line) => line.trim()).find((line) => line.length > 0) || "",
      80,
    );
    const suffix = lines.length > 1 ? ` ... (${lines.length} lines)` : "";
    return countWrappedLines(
      `▸ ● ${firstLine || "(empty)"}${suffix}`,
      w.content,
    );
  }
  const rendered = renderMarkdown(item.content, w.content);
  return 1 + countWrappedLines(rendered, w.indented);
}

function estimateItemHeight(
  item: ChatItem,
  expanded: boolean,
  width: number,
): number {
  const w: Widths = {
    content: Math.max(10, width),
    indented: Math.max(10, width - 2),
    deepIndented: Math.max(10, width - 4),
  };

  switch (item.kind) {
    case "user_message":
      return estimateUserMessageHeight(item, w);
    case "thinking":
      return estimateThinkingHeight(item, expanded, w);
    case "tool_call":
      return estimateToolCallHeight(item, expanded, w);
    case "tool_group": {
      if (expanded) return 1 + item.calls.length;
      const lastHasResult =
        item.calls[item.calls.length - 1]?.resultStep?.result;
      return lastHasResult ? 2 : 1;
    }
    case "intermediate":
      return estimateIntermediateHeight(item, expanded, w);
    case "final_answer":
      return estimateFinalAnswerHeight(item, expanded, w);
    case "streaming":
      return estimateStreamingHeight(item, w);
    default:
      return 1;
  }
}

function computeScrollOffset(
  prev: number,
  opts: {
    topOfSelected: number;
    bottomOfSelected: number;
    selectedHeight: number;
    height: number;
    totalHeight: number;
    autoScrollToBottom: boolean;
    movedUp: boolean;
  },
): number {
  const { topOfSelected, bottomOfSelected, height, totalHeight } = opts;
  let next = prev;

  if (opts.selectedHeight > height && opts.autoScrollToBottom) {
    next = bottomOfSelected - height;
  } else if (opts.selectedHeight > height && opts.movedUp) {
    // When moving up into a tall item, align to its top
    if (topOfSelected < next) next = topOfSelected;
    else if (bottomOfSelected > next + height) next = bottomOfSelected - height;
  } else {
    if (bottomOfSelected > next + height) next = bottomOfSelected - height;
    if (topOfSelected < next) next = topOfSelected;
  }

  return Math.max(0, Math.min(next, totalHeight - height));
}

export const ChatView = React.memo(function ChatView({
  items,
  expandState,
  selectedIndex,
  height,
  width,
  browseMode,
  autoScrollToBottom,
  scrollNudge,
}: ChatViewProps) {
  const [scrollOffset, setScrollOffset] = useState(0);
  const prevSelectedRef = useRef(selectedIndex);
  const prevScrollNudgeRef = useRef(scrollNudge);
  const emptyStateCircle = useMemo(
    () => buildRossumCircle(width, height),
    [width, height],
  );

  const heights = useMemo(
    () =>
      items.map((item, i) => estimateItemHeight(item, !!expandState[i], width)),
    [items, expandState, width],
  );

  const totalHeight = useMemo(
    () => heights.reduce((a, b) => a + b, 0),
    [heights],
  );

  useEffect(() => {
    if (totalHeight <= height) {
      setScrollOffset(0);
      prevSelectedRef.current = selectedIndex;
      return;
    }

    const movedUp = selectedIndex < prevSelectedRef.current;
    let topOfSelected = 0;
    for (let i = 0; i < selectedIndex; i++) {
      topOfSelected += heights[i] ?? 1;
    }
    const selectedHeight = heights[selectedIndex] ?? 1;
    const bottomOfSelected = topOfSelected + selectedHeight;

    setScrollOffset((prev) =>
      computeScrollOffset(prev, {
        topOfSelected,
        bottomOfSelected,
        selectedHeight,
        height,
        totalHeight,
        autoScrollToBottom,
        movedUp,
      }),
    );
    prevSelectedRef.current = selectedIndex;
  }, [heights, totalHeight, selectedIndex, height, autoScrollToBottom]);

  useEffect(() => {
    const delta = scrollNudge - prevScrollNudgeRef.current;
    prevScrollNudgeRef.current = scrollNudge;
    if (delta === 0) return;

    setScrollOffset((prev) =>
      Math.max(0, Math.min(prev + delta, Math.max(totalHeight - height, 0))),
    );
  }, [scrollNudge, totalHeight, height]);

  const { startIdx, endIdx } = useMemo(() => {
    let cumulative = 0;
    let start = 0;
    for (let i = 0; i < items.length; i++) {
      if (cumulative + (heights[i] ?? 1) > scrollOffset) {
        start = i;
        break;
      }
      cumulative += heights[i] ?? 1;
    }

    let end = start;
    let visibleUsed = cumulative - scrollOffset;
    for (let i = start; i < items.length; i++) {
      visibleUsed += heights[i] ?? 1;
      end = i;
      if (visibleUsed >= height) break;
    }

    return { startIdx: start, endIdx: Math.min(end + 1, items.length) };
  }, [items.length, heights, scrollOffset, height]);

  return (
    <Box flexDirection="column" height={height} overflowY="hidden">
      {items.length === 0 ? (
        <Box
          flexDirection="column"
          flexGrow={1}
          justifyContent="center"
          alignItems="center"
        >
          <Box flexDirection="column">
            {emptyStateCircle.map((line, i) => (
              <Text key={i} color="blueBright">
                {line}
              </Text>
            ))}
            <Text dimColor> </Text>
            <Text dimColor>Type a message to start.</Text>
            <Text dimColor>Use / for commands and @path to attach files.</Text>
            <Text dimColor>
              Esc: browse history, Ctrl+X: stop, Ctrl+N: new chat
            </Text>
          </Box>
        </Box>
      ) : (
        items.slice(startIdx, endIdx).map((item, visIdx) => {
          const i = startIdx + visIdx;
          return (
            <Box key={i} flexDirection="column">
              <ChatItemDisplay
                item={item}
                expanded={!!expandState[i]}
                selected={browseMode && i === selectedIndex}
              />
            </Box>
          );
        })
      )}
    </Box>
  );
});
