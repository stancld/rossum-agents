import { createParser, type EventSourceMessage } from "eventsource-parser";
import { buildHeaders } from "./client.js";
import type { Config, SSEEvent } from "../types.js";
import type {
  ImageAttachment,
  DocumentAttachment,
} from "../utils/fileAttachments.js";

export interface StreamOptions {
  config: Config;
  chatId: string;
  message: string;
  images?: ImageAttachment[];
  documents?: DocumentAttachment[];
  onEvent: (event: SSEEvent) => void;
  onError: (error: Error) => void;
  onDone: () => void;
  signal?: AbortSignal;
}

function buildRequestBody(
  opts: Pick<StreamOptions, "message" | "images" | "documents"> & {
    persona: string;
  },
): string {
  const body: Record<string, unknown> = {
    content: opts.message,
    persona: opts.persona,
  };
  if (opts.images && opts.images.length > 0) body.images = opts.images;
  if (opts.documents && opts.documents.length > 0)
    body.documents = opts.documents;
  return JSON.stringify(body);
}

function formatFetchError(err: unknown, apiUrl: string): Error {
  const cause =
    err instanceof TypeError && err.cause
      ? (err.cause as { code?: string; message?: string })
      : null;
  const detail =
    cause?.code ||
    cause?.message ||
    (err instanceof Error ? err.message : String(err));
  return new Error(`Cannot connect to ${apiUrl}: ${detail}`);
}

async function readStream(
  body: ReadableStream<Uint8Array>,
  parser: ReturnType<typeof createParser>,
  onDone: () => void,
  signal?: AbortSignal,
  onError?: (error: Error) => void,
): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      parser.feed(decoder.decode(value, { stream: true }));
    }
    onDone();
  } catch (e) {
    if (signal?.aborted) return;
    onError?.(e instanceof Error ? e : new Error(String(e)));
  }
}

export async function streamMessage(opts: StreamOptions): Promise<void> {
  const { config, chatId, onEvent, onError, onDone, signal } = opts;

  let res: Response;
  try {
    res = await fetch(`${config.apiUrl}/api/v1/chats/${chatId}/messages`, {
      method: "POST",
      headers: buildHeaders(config),
      body: buildRequestBody({ ...opts, persona: config.persona }),
      signal,
    });
  } catch (err) {
    if (signal?.aborted) return;
    onError(formatFetchError(err, config.apiUrl));
    return;
  }

  if (!res.ok) {
    const text = await res.text();
    onError(new Error(`Stream request failed (${res.status}): ${text}`));
    return;
  }

  if (!res.body) {
    onError(new Error("Response body is null"));
    return;
  }

  const parser = createParser({
    onEvent(event: EventSourceMessage) {
      try {
        const data = JSON.parse(event.data);
        const eventType = event.event || "step";
        onEvent({ event: eventType, data } as SSEEvent);
      } catch {
        onError(new Error(`Failed to parse SSE data: ${event.data}`));
      }
    },
  });

  await readStream(res.body, parser, onDone, signal, onError);
}
