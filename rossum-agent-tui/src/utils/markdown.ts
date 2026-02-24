import { type MarkedExtension, marked } from "marked";
import { markedTerminal } from "marked-terminal";

// markedTerminal() returns a MarkedExtension but types declare TerminalRenderer
marked.use(
  markedTerminal({ width: process.stdout.columns || 80 }) as MarkedExtension,
);

export function renderMarkdown(text: string): string {
  try {
    const result = marked.parse(text) as string;
    return result.trimEnd();
  } catch {
    return text;
  }
}
