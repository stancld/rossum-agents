import React, { useState, useEffect, useMemo } from "react";
import { Box } from "ink";
import { ChatItemDisplay } from "./ChatItemDisplay.js";
import type { ChatItem, ExpandState } from "../types.js";

interface ChatViewProps {
  items: ChatItem[];
  expandState: ExpandState;
  selectedIndex: number;
  height: number;
  browseMode: boolean;
}

function estimateItemHeight(item: ChatItem, expanded: boolean): number {
  if (item.kind === "user_message") return 1;
  if (item.kind === "thinking") {
    return expanded ? Math.max(1, item.content.split("\n").length + 1) : 1;
  }
  if (item.kind === "tool_call") {
    if (!expanded) return item.resultStep?.result ? 2 : 1;
    let h = 1;
    if (item.step.toolArguments) {
      h += Object.keys(item.step.toolArguments).filter(
        (k) => k !== "connection_id" && k !== "tool_name",
      ).length;
    }
    if (item.resultStep?.result) {
      h += 1 + item.resultStep.result.split("\n").length;
    }
    return h;
  }
  if (item.kind === "intermediate") {
    const lines = item.content.split("\n").length;
    if (lines <= 5) return lines;
    return expanded ? lines + 1 : 2;
  }
  if (item.kind === "final_answer") {
    return Math.max(1, item.content.split("\n").length);
  }
  if (item.kind === "streaming") return 2;
  return 1;
}

export const ChatView = React.memo(function ChatView({
  items,
  expandState,
  selectedIndex,
  height,
  browseMode,
}: ChatViewProps) {
  const [scrollOffset, setScrollOffset] = useState(0);

  const heights = useMemo(
    () => items.map((item, i) => estimateItemHeight(item, !!expandState[i])),
    [items, expandState],
  );

  const totalHeight = useMemo(
    () => heights.reduce((a, b) => a + b, 0),
    [heights],
  );

  useEffect(() => {
    if (totalHeight <= height) {
      setScrollOffset(0);
      return;
    }

    let topOfSelected = 0;
    for (let i = 0; i < selectedIndex; i++) {
      topOfSelected += heights[i] ?? 1;
    }
    const bottomOfSelected = topOfSelected + (heights[selectedIndex] ?? 1);

    setScrollOffset((prev) => {
      let next = prev;
      if (bottomOfSelected > next + height) {
        next = bottomOfSelected - height;
      }
      if (topOfSelected < next) {
        next = topOfSelected;
      }
      return Math.max(0, Math.min(next, totalHeight - height));
    });
  }, [heights, totalHeight, selectedIndex, height]);

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
      {items.slice(startIdx, endIdx).map((item, visIdx) => {
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
      })}
    </Box>
  );
});
