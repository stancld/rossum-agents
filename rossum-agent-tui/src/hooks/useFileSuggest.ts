import { useState, useEffect, useRef, useCallback } from "react";
import {
  listDirectory,
  searchFiles,
  type FileEntry,
} from "../utils/fileAttachments.js";

export interface FileSuggestState {
  entries: FileEntry[];
  selectedIndex: number;
  visible: boolean;
  loading: boolean;
  partialPath: string;
}

// Walk backwards from cursor to find the @ token being typed.
// Returns the partial path after @ (e.g. "~/Do" from "@~/Do"), or null if
// the cursor is not in an @ context.
function extractAtContext(
  text: string,
  cursorRow: number,
  cursorCol: number,
): string | null {
  const lines = text.split("\n");
  const line = lines[cursorRow];
  if (!line) return null;

  const before = line.slice(0, cursorCol);
  // Find the last @ that starts a path token (at start of line or after whitespace)
  const match = before.match(/(?:^|\s)@([^\s]*)$/);
  if (!match) return null;
  return match[1]!;
}

export function useFileSuggest(
  text: string,
  cursorRow: number,
  cursorCol: number,
) {
  const [entries, setEntries] = useState<FileEntry[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const partialPath = extractAtContext(text, cursorRow, cursorCol);
  const visible = partialPath !== null;

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);

    if (!visible || partialPath === null) {
      setEntries([]);
      setSelectedIndex(0);
      return;
    }

    setLoading(true);
    // Bare names (no path separator) trigger recursive search across the tree;
    // paths with separators use flat directory listing as before.
    const isBareQuery = partialPath !== "" && !partialPath.includes("/");
    timerRef.current = setTimeout(() => {
      const results = isBareQuery
        ? searchFiles(partialPath)
        : listDirectory(partialPath);
      setEntries(results);
      setSelectedIndex(0);
      setLoading(false);
    }, 50);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [partialPath, visible]);

  const moveUp = useCallback(() => {
    setSelectedIndex((prev) => Math.max(prev - 1, 0));
  }, []);

  const moveDown = useCallback(() => {
    setSelectedIndex((prev) => Math.min(prev + 1, entries.length - 1));
  }, [entries.length]);

  const getSelectedEntry = useCallback((): FileEntry | null => {
    return entries[selectedIndex] ?? null;
  }, [entries, selectedIndex]);

  return {
    entries,
    selectedIndex,
    visible,
    loading,
    partialPath: partialPath ?? "",
    moveUp,
    moveDown,
    getSelectedEntry,
  };
}
