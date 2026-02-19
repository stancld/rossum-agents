#!/usr/bin/env node
import React from "react";
import { render } from "ink";
import meow from "meow";
import { App } from "./app.js";
import { resolveConfig } from "./hooks/useConfig.js";

const cli = meow(
  `
  Usage
    $ rossum-agent-tui [options]

  Options
    --api-url      Agent API URL (env: ROSSUM_AGENT_API_URL)
    --token        Rossum API token (env: ROSSUM_API_TOKEN)
    --rossum-url   Rossum API base URL (env: ROSSUM_API_BASE_URL)
    --mcp-mode     MCP mode: read-only | read-write (default: read-only)
    --persona      Agent persona: default | cautious (default: default)

  Examples
    $ rossum-agent-tui --api-url http://localhost:8000
    $ ROSSUM_AGENT_API_URL=http://localhost:8000 rossum-agent-tui
`,
  {
    importMeta: import.meta,
    flags: {
      apiUrl: { type: "string" },
      token: { type: "string" },
      rossumUrl: { type: "string" },
      mcpMode: { type: "string" },
      persona: { type: "string" },
    },
  },
);

try {
  const config = resolveConfig(cli.flags);
  render(<App config={config} />);
} catch (err) {
  console.error(err instanceof Error ? err.message : String(err));
  process.exit(1);
}
