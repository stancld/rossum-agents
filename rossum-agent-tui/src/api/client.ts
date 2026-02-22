import type {
  ChatResponse,
  ChatListResponse,
  CommandInfo,
  Config,
} from "../types.js";

export function buildHeaders(config: Config): Record<string, string> {
  return {
    "Content-Type": "application/json",
    "X-Rossum-Token": config.token,
    "X-Rossum-Api-Url": config.rossumUrl,
  };
}

function unwrapFetchError(err: unknown, context: string): Error {
  if (err instanceof TypeError && err.cause) {
    const cause = err.cause as { code?: string; message?: string };
    return new Error(
      `${context}: ${cause.code || cause.message || err.message}`,
    );
  }
  return err instanceof Error ? err : new Error(String(err));
}

export async function createChat(config: Config): Promise<ChatResponse> {
  let res: Response;
  try {
    res = await fetch(`${config.apiUrl}/api/v1/chats`, {
      method: "POST",
      headers: buildHeaders(config),
      body: JSON.stringify({
        mcp_mode: config.mcpMode,
        persona: config.persona,
      }),
    });
  } catch (err) {
    throw unwrapFetchError(err, `Cannot connect to ${config.apiUrl}`);
  }
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Failed to create chat (${res.status}): ${body}`);
  }
  return (await res.json()) as ChatResponse;
}

export async function listCommands(config: Config): Promise<CommandInfo[]> {
  try {
    const res = await fetch(`${config.apiUrl}/api/v1/commands`, {
      headers: buildHeaders(config),
    });
    if (!res.ok) {
      return [];
    }
    const data = (await res.json()) as { commands: CommandInfo[] };
    return data.commands;
  } catch {
    return [];
  }
}

export async function listChats(
  config: Config,
  limit = 50,
  offset = 0,
): Promise<ChatListResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  const res = await fetch(
    `${config.apiUrl}/api/v1/chats?${params.toString()}`,
    { headers: buildHeaders(config) },
  );
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Failed to list chats (${res.status}): ${body}`);
  }
  return (await res.json()) as ChatListResponse;
}
