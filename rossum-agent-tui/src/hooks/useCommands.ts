import { useState, useEffect } from "react";
import { listCommands } from "../api/client.js";
import type { CommandInfo, Config } from "../types.js";

const FALLBACK_COMMANDS: CommandInfo[] = [
  { name: "/list-commands", description: "List all available slash commands" },
  {
    name: "/list-commits",
    description: "List configuration commits made in this chat",
  },
  { name: "/list-skills", description: "List available agent skills" },
  { name: "/list-mcp-tools", description: "List MCP tools by category" },
  { name: "/list-agent-tools", description: "List built-in agent tools" },
];

export function useCommands(config: Config): { commands: CommandInfo[] } {
  const [commands, setCommands] = useState<CommandInfo[]>(FALLBACK_COMMANDS);

  useEffect(() => {
    let cancelled = false;
    listCommands(config).then((result) => {
      if (!cancelled && result.length > 0) {
        setCommands(result);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [config]);

  return { commands };
}
