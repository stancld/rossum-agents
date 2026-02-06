import type { Config, McpMode } from "../types.js";

interface CliFlags {
  apiUrl?: string;
  token?: string;
  rossumUrl?: string;
  mcpMode?: string;
}

function resolve(
  flagValue: string | undefined,
  envVar: string,
): string | undefined {
  return flagValue || process.env[envVar];
}

function requireValue(value: string | undefined, name: string): string {
  if (value) return value;
  throw new Error(`Missing required configuration: ${name}`);
}

export function resolveConfig(flags: CliFlags): Config {
  const apiUrl = requireValue(
    resolve(flags.apiUrl, "ROSSUM_AGENT_API_URL"),
    "--api-url or ROSSUM_AGENT_API_URL",
  );
  const token = requireValue(
    resolve(flags.token, "ROSSUM_API_TOKEN"),
    "--token or ROSSUM_API_TOKEN",
  );
  const rossumUrl = requireValue(
    resolve(flags.rossumUrl, "ROSSUM_API_BASE_URL"),
    "--rossum-url or ROSSUM_API_BASE_URL",
  );

  const mcpModeRaw =
    flags.mcpMode || process.env["ROSSUM_MCP_MODE"] || "read-only";
  if (mcpModeRaw !== "read-only" && mcpModeRaw !== "read-write") {
    throw new Error(
      `Invalid MCP mode: ${mcpModeRaw}. Must be 'read-only' or 'read-write'.`,
    );
  }

  return { apiUrl, token, rossumUrl, mcpMode: mcpModeRaw as McpMode };
}
