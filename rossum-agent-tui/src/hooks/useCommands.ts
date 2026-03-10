import { useState, useEffect } from "react";
import { listCommands } from "../api/client.js";
import type { CommandInfo, Config } from "../types.js";

const FALLBACK_COMMANDS: CommandInfo[] = [
  {
    name: "/list-commands",
    description: "List all available slash commands",
    argument_suggestions: [],
  },
  {
    name: "/list-commits",
    description: "List configuration commits made in this chat",
    argument_suggestions: [],
  },
  {
    name: "/list-skills",
    description: "List available agent skills",
    argument_suggestions: [],
  },
  {
    name: "/list-mcp-tools",
    description: "List MCP tools by category",
    argument_suggestions: [],
  },
  {
    name: "/list-agent-tools",
    description: "List built-in agent tools",
    argument_suggestions: [],
  },
  {
    name: "/persona",
    description: "Get or switch the agent persona (e.g. `/persona cautious`)",
    argument_suggestions: [
      {
        value: "default",
        description:
          "Balanced mode — acts autonomously, asks only when truly ambiguous",
      },
      {
        value: "cautious",
        description:
          "Plans first, asks before writes, verifies before and after changes",
      },
    ],
  },
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
