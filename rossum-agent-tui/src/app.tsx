import React, {
  useState,
  useCallback,
  useEffect,
  useMemo,
  useRef,
} from "react";
import { Box, useInput } from "ink";
import { ChatView } from "./components/ChatView.js";
import { InputArea } from "./components/InputArea.js";
import { QuestionSelector } from "./components/QuestionSelector.js";
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
  AgentQuestionItem,
  AttachmentInfo,
  Config,
  ExpandState,
  InteractionMode,
} from "./types.js";

interface ProcessedAttachments {
  images: ImageAttachment[];
  documents: DocumentAttachment[];
  textFiles: TextAttachment[];
  attachmentInfos: AttachmentInfo[];
  errors: string[];
}

function processAttachments(paths: string[]): ProcessedAttachments {
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

  return { images, documents, textFiles, attachmentInfos, errors };
}

function buildMessageContent(
  message: string,
  textFiles: TextAttachment[],
  errors: string[],
): string {
  let content = message.replace(/\s+/g, " ").trim();
  if (!content && textFiles.length === 0) {
    content = "See attached files.";
  }

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

  return content;
}

function buildDisplayMessage(message: string): string {
  const cleaned = message.replace(/\s+/g, " ").trim();
  return cleaned || "See attached files.";
}

interface AppProps {
  config: Config;
}

function isExpandable(kind: string): boolean {
  return (
    kind === "thinking" ||
    kind === "tool_call" ||
    kind === "tool_group" ||
    kind === "intermediate" ||
    kind === "final_answer"
  );
}

export function App({ config }: AppProps) {
  const { state, sendMessage, resetChat, abortStreaming, submitFeedback } =
    useChat(config);
  const { commands } = useCommands(config);
  const { rows, columns } = useTerminalSize();

  const [mode, setMode] = useState<InteractionMode>("input");
  const [expandState, setExpandState] = useState<ExpandState>({});
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [autoScroll, setAutoScroll] = useState(true);
  const [inputAreaRows, setInputAreaRows] = useState(1);
  const [scrollNudge, setScrollNudge] = useState(0);
  const [questionIndex, setQuestionIndex] = useState(0);
  const [questionAnswers, setQuestionAnswers] = useState<string[]>([]);
  const [otherSelected, setOtherSelected] = useState(false);

  // Reset question iteration state when a new question event arrives
  const pendingRef = useRef(state.pendingQuestion);
  useEffect(() => {
    if (state.pendingQuestion !== pendingRef.current) {
      pendingRef.current = state.pendingQuestion;
      setQuestionIndex(0);
      setQuestionAnswers([]);
      setOtherSelected(false);
    }
  }, [state.pendingQuestion]);

  const items = useMemo(
    () => buildChatItems(state, questionIndex),
    [state, questionIndex],
  );

  // Layout: ChatView (flex) + InputArea (1+ rows) + TaskList (N rows) + StatusBar (3 rows with border)
  const taskListHeight = state.tasks.length;
  const fixedHeight = 3 + inputAreaRows + taskListHeight; // statusBar + input + taskList
  const chatAreaHeight = Math.max(rows - fixedHeight, 1);

  useEffect(() => {
    if (autoScroll && items.length > 0) {
      const lastIndex = items.length - 1;
      setSelectedIndex((prev) => (prev === lastIndex ? prev : lastIndex));
    }
  }, [items, autoScroll]);

  useEffect(() => {
    let latestFinalAnswerIndex = -1;
    for (let i = items.length - 1; i >= 0; i--) {
      if (items[i]?.kind === "final_answer") {
        latestFinalAnswerIndex = i;
        break;
      }
    }

    setExpandState((prev) => {
      let changed = false;
      const next = { ...prev };
      items.forEach((item, i) => {
        if (isExpandable(item.kind) && !(i in next)) {
          next[i] =
            item.kind === "final_answer" && i === latestFinalAnswerIndex;
          changed = true;
        }
      });
      return changed ? next : prev;
    });
  }, [items]);

  const handleSendMessage = useCallback(
    async (message: string) => {
      setAutoScroll(true);
      setExpandState({});

      const paths = parseAtTokens(message);
      if (paths.length === 0) {
        sendMessage(message);
        return;
      }

      const { images, documents, textFiles, attachmentInfos, errors } =
        processAttachments(paths);
      const content = buildMessageContent(message, textFiles, errors);
      const displayMessage = buildDisplayMessage(message);

      sendMessage(content, {
        displayMessage,
        images: images.length > 0 ? images : undefined,
        documents: documents.length > 0 ? documents : undefined,
        attachmentInfos:
          attachmentInfos.length > 0 ? attachmentInfos : undefined,
      });
    },
    [sendMessage],
  );

  const handleQuestionAnswer = useCallback(
    (answer: string) => {
      const pq = state.pendingQuestion;
      if (!pq) return;

      const updatedAnswers = [...questionAnswers, answer];
      if (updatedAnswers.length < pq.questions.length) {
        setQuestionAnswers(updatedAnswers);
        setQuestionIndex(updatedAnswers.length);
        setOtherSelected(false);
        return;
      }

      // All questions answered — format combined answer and send
      const combined = pq.questions
        .map(
          (q: AgentQuestionItem, i: number) =>
            `${i + 1}. ${q.question}\n${updatedAnswers[i]}`,
        )
        .join("\n\n");
      setAutoScroll(true);
      setExpandState({});
      sendMessage(combined);
    },
    [state.pendingQuestion, questionAnswers, sendMessage],
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

  const handleBrowseNavigation = useCallback(
    (input: string, key: { downArrow: boolean; upArrow: boolean }) => {
      if (input === "j" || key.downArrow) {
        setSelectedIndex((prev) => {
          const next = Math.min(prev + 1, items.length - 1);
          if (next === items.length - 1) setAutoScroll(true);
          return next;
        });
        return true;
      }
      if (input === "k" || key.upArrow) {
        setSelectedIndex((prev) => {
          if (prev > 0) setAutoScroll(false);
          return Math.max(prev - 1, 0);
        });
        return true;
      }
      if (input === "G") {
        setSelectedIndex(Math.max(items.length - 1, 0));
        setAutoScroll(true);
        return true;
      }
      return false;
    },
    [items.length],
  );

  const handleBrowseScroll = useCallback(
    (input: string, key: { ctrl: boolean }) => {
      if (!key.ctrl) return false;
      const half = Math.max(Math.floor(chatAreaHeight / 2), 1);
      if (input === "d") {
        setAutoScroll(false);
        setScrollNudge((prev) => prev + half);
        return true;
      }
      if (input === "u") {
        setAutoScroll(false);
        setScrollNudge((prev) => prev - half);
        return true;
      }
      return false;
    },
    [chatAreaHeight],
  );

  const handleBrowseFeedback = useCallback(
    (input: string) => {
      if (input !== "+" && input !== "-") return false;
      const item = items[selectedIndex];
      if (item && item.kind === "final_answer") {
        submitFeedback(item.turnIndex, input === "+");
      }
      return true;
    },
    [items, selectedIndex, submitFeedback],
  );

  useInput(
    (input, key) => {
      if (input === "i" || key.tab) {
        setMode("input");
        return;
      }
      if (handleBrowseNavigation(input, key)) return;
      if (handleBrowseScroll(input, key)) return;
      if (handleBrowseFeedback(input)) return;

      if (key.return || input === " ") {
        const item = items[selectedIndex];
        if (item && isExpandable(item.kind)) {
          setExpandState((prev) => ({
            ...prev,
            [selectedIndex]: !prev[selectedIndex],
          }));
        }
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
    if (input === "x" && key.ctrl) {
      abortStreaming();
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

  return (
    <Box flexDirection="column" height={rows} overflow="hidden">
      <ChatView
        items={items}
        expandState={expandState}
        selectedIndex={selectedIndex}
        height={chatAreaHeight}
        width={columns}
        browseMode={mode === "browse"}
        autoScrollToBottom={autoScroll && selectedIndex === items.length - 1}
        scrollNudge={scrollNudge}
      />
      {state.pendingQuestion &&
      !otherSelected &&
      (state.pendingQuestion.questions[questionIndex]?.options ?? []).length ? (
        <QuestionSelector
          key={questionIndex}
          options={
            state.pendingQuestion.questions[questionIndex]!.options ?? []
          }
          multiSelect={
            state.pendingQuestion.questions[questionIndex]!.multi_select
          }
          onSubmit={handleQuestionAnswer}
          onOtherSelected={() => setOtherSelected(true)}
          mode={mode}
          onHeightChange={setInputAreaRows}
        />
      ) : (
        <InputArea
          onSubmit={
            state.pendingQuestion ? handleQuestionAnswer : handleSendMessage
          }
          connectionStatus={state.connectionStatus}
          mode={mode}
          commands={state.pendingQuestion ? [] : commands}
          onHeightChange={setInputAreaRows}
        />
      )}
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
