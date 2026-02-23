import React, {
  useState,
  useCallback,
  useEffect,
  useRef,
  useMemo,
} from "react";
import { Box, useInput } from "ink";
import { ChatView } from "./components/ChatView.js";
import { InputArea } from "./components/InputArea.js";
import { StatusBar } from "./components/StatusBar.js";
import { TaskList } from "./components/TaskList.js";
import { useChat } from "./hooks/useChat.js";
import { useCommands } from "./hooks/useCommands.js";
import { useTerminalSize } from "./hooks/useTerminalSize.js";
import { buildChatItems } from "./utils/buildChatItems.js";
import {
  parseAtTokens,
  readAttachment,
  type ImageAttachment,
  type DocumentAttachment,
  type TextAttachment,
} from "./utils/fileAttachments.js";
import type {
  AttachmentInfo,
  Config,
  ExpandState,
  InteractionMode,
} from "./types.js";

interface AppProps {
  config: Config;
}

function isExpandable(kind: string): boolean {
  return kind === "thinking" || kind === "tool_call" || kind === "intermediate";
}

export function App({ config }: AppProps) {
  const { state, sendMessage, resetChat } = useChat(config);
  const { commands } = useCommands(config);
  const { rows } = useTerminalSize();

  const [mode, setMode] = useState<InteractionMode>("input");
  const [expandState, setExpandState] = useState<ExpandState>({});
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [autoScroll, setAutoScroll] = useState(true);
  const [suggestionRows, setSuggestionRows] = useState(0);

  const items = useMemo(() => buildChatItems(state), [state]);
  const prevItemsLenRef = useRef(items.length);

  useEffect(() => {
    if (
      autoScroll &&
      items.length > 0 &&
      items.length !== prevItemsLenRef.current
    ) {
      setSelectedIndex(items.length - 1);
    }
    prevItemsLenRef.current = items.length;
  }, [items.length, autoScroll]);

  useEffect(() => {
    setExpandState((prev) => {
      let changed = false;
      const next = { ...prev };
      items.forEach((item, i) => {
        if (isExpandable(item.kind) && !(i in next)) {
          next[i] = false;
          changed = true;
        }
      });
      return changed ? next : prev;
    });
  }, [items]);

  const handleSendMessage = useCallback(
    async (message: string) => {
      setAutoScroll(true);

      const paths = parseAtTokens(message);
      if (paths.length === 0) {
        sendMessage(message);
        return;
      }

      const images: ImageAttachment[] = [];
      const documents: DocumentAttachment[] = [];
      const textFiles: TextAttachment[] = [];
      const attachmentInfos: AttachmentInfo[] = [];
      const errors: string[] = [];

      for (const filePath of paths) {
        try {
          const attachment = readAttachment(filePath);
          if (attachment.type === "image") {
            if (images.length < 5) {
              images.push(attachment);
              attachmentInfos.push({
                filename: filePath.split("/").pop() ?? filePath,
                type: "image",
              });
            }
          } else if (attachment.type === "text") {
            textFiles.push(attachment);
            attachmentInfos.push({
              filename: attachment.filename,
              type: "text",
            });
          } else {
            if (documents.length < 5) {
              documents.push(attachment);
              attachmentInfos.push({
                filename: attachment.filename,
                type: "document",
              });
            }
          }
        } catch (err) {
          errors.push(
            `${filePath}: ${err instanceof Error ? err.message : String(err)}`,
          );
        }
      }

      let content = message.replace(/\s+/g, " ").trim();
      if (!content && textFiles.length === 0) {
        content = "See attached files.";
      }

      // Inline text file contents into the message
      if (textFiles.length > 0) {
        const inlined = textFiles
          .map(
            (f) =>
              `<file_content path="${f.filename}">\n${f.content}\n</file_content>`,
          )
          .join("\n\n");
        content = content ? `${content}\n\n${inlined}` : inlined;
      }

      if (errors.length > 0) {
        content += "\n\n[Attachment errors: " + errors.join("; ") + "]";
      }

      sendMessage(content, {
        images: images.length > 0 ? images : undefined,
        documents: documents.length > 0 ? documents : undefined,
        attachmentInfos:
          attachmentInfos.length > 0 ? attachmentInfos : undefined,
      });
    },
    [sendMessage],
  );

  const sendQuickReply = useCallback(
    (message: string) => {
      if (mode !== "input") return;
      if (
        state.connectionStatus === "connecting" ||
        state.connectionStatus === "streaming"
      ) {
        return;
      }
      handleSendMessage(message);
    },
    [handleSendMessage, mode, state.connectionStatus],
  );

  useInput(
    (input, key) => {
      if (input === "i" || key.tab) {
        setMode("input");
        return;
      }

      if (input === "j" || key.downArrow) {
        setSelectedIndex((prev) => {
          const next = Math.min(prev + 1, items.length - 1);
          if (next === items.length - 1) setAutoScroll(true);
          return next;
        });
        return;
      }

      if (input === "k" || key.upArrow) {
        setSelectedIndex((prev) => {
          if (prev > 0) setAutoScroll(false);
          return Math.max(prev - 1, 0);
        });
        return;
      }

      if (key.return || input === " ") {
        const item = items[selectedIndex];
        if (item && isExpandable(item.kind)) {
          setExpandState((prev) => ({
            ...prev,
            [selectedIndex]: !prev[selectedIndex],
          }));
        }
        return;
      }

      if (input === "G") {
        setSelectedIndex(Math.max(items.length - 1, 0));
        setAutoScroll(true);
        return;
      }
    },
    { isActive: mode === "browse" },
  );

  useInput(
    (_input, key) => {
      if (key.escape) {
        setMode("browse");
        if (items.length > 0) {
          setSelectedIndex(items.length - 1);
        }
      }
    },
    { isActive: mode === "input" },
  );

  useInput((input, key) => {
    if (input === "n" && key.ctrl) {
      resetChat();
      setExpandState({});
      setSelectedIndex(0);
      setAutoScroll(true);
      setMode("input");
    }
  });

  useInput((input, key) => {
    if (!key.meta) return;
    if (input === "1") {
      sendQuickReply("Approve");
      return;
    }
    if (input === "2") {
      sendQuickReply("Reject");
      return;
    }
    if (input === "3") {
      sendQuickReply("Let's chat about it.");
    }
  });

  // Layout: ChatView (flex) + InputArea (1+ rows) + TaskList (N rows) + StatusBar (3 rows with border)
  const taskListHeight = state.tasks.length;
  const inputHeight = 1 + suggestionRows;
  const fixedHeight = 3 + inputHeight + taskListHeight; // statusBar + input + taskList
  const chatAreaHeight = Math.max(rows - fixedHeight, 3);

  return (
    <Box flexDirection="column" height={rows} overflow="hidden">
      <ChatView
        items={items}
        expandState={expandState}
        selectedIndex={selectedIndex}
        height={chatAreaHeight}
        browseMode={mode === "browse"}
      />
      <InputArea
        onSubmit={handleSendMessage}
        connectionStatus={state.connectionStatus}
        mode={mode}
        commands={commands}
        onSuggestionRowsChange={setSuggestionRows}
      />
      {state.tasks.length > 0 && <TaskList tasks={state.tasks} />}
      <StatusBar
        connectionStatus={state.connectionStatus}
        mcpMode={config.mcpMode}
        persona={config.persona}
        chatId={state.chatId}
        tokenUsage={state.tokenUsage}
        mode={mode}
      />
    </Box>
  );
}
