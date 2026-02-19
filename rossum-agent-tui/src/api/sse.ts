import { createParser, type EventSourceMessage } from "eventsource-parser";
import { buildHeaders } from "./client.js";
import type { Config, SSEEvent } from "../types.js";

export interface StreamOptions {
  config: Config;
  chatId: string;
  message: string;
  onEvent: (event: SSEEvent) => void;
  onError: (error: Error) => void;
  onDone: () => void;
  signal?: AbortSignal;
}

export async function streamMessage(opts: StreamOptions): Promise<void> {
  const { config, chatId, message, onEvent, onError, onDone, signal } = opts;

  let res: Response;
  try {
    res = await fetch(`${config.apiUrl}/api/v1/chats/${chatId}/messages`, {
      method: "POST",
      headers: buildHeaders(config),
      body: JSON.stringify({ content: message, persona: config.persona }),
      signal,
    });
  } catch (err) {
    if (signal?.aborted) return;
    const cause =
      err instanceof TypeError && err.cause
        ? (err.cause as { code?: string; message?: string })
        : null;
    onError(
      new Error(
        `Cannot connect to ${config.apiUrl}: ${cause?.code || cause?.message || (err instanceof Error ? err.message : String(err))}`,
      ),
    );
    return;
  }

  if (!res.ok) {
    const body = await res.text();
    onError(new Error(`Stream request failed (${res.status}): ${body}`));
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
      } catch (e) {
        onError(new Error(`Failed to parse SSE data: ${event.data}`));
      }
    },
  });

  const reader = res.body.getReader();
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
    onError(e instanceof Error ? e : new Error(String(e)));
  }
}
