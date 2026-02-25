import { type MarkedExtension, type Token, marked } from "marked";
import { markedTerminal } from "marked-terminal";

interface TerminalRendererExtension extends MarkedExtension {
  renderer?: {
    text?: (token: Token) => string;
  };
}

function hasInlineTokens(token: Token): token is Token & { tokens: Token[] } {
  return "tokens" in token && Array.isArray(token.tokens);
}

// markedTerminal() returns a MarkedExtension at runtime, but @types declares
// TerminalRenderer. We also patch `text` rendering so inline tokens nested in
// list-item text (e.g. markdown links) are rendered instead of printed raw.
const terminalExtension = markedTerminal({
  width: process.stdout.columns || 80,
}) as TerminalRendererExtension;
const renderText = terminalExtension.renderer?.text;
if (renderText && terminalExtension.renderer) {
  terminalExtension.renderer.text = function (
    this: { parser?: { parseInline: (tokens: Token[]) => string } },
    token: Token,
  ): string {
    if (hasInlineTokens(token) && this.parser) {
      return this.parser.parseInline(token.tokens);
    }
    return renderText.call(this, token);
  };
}
marked.use(terminalExtension as MarkedExtension);

export function renderMarkdown(text: string): string {
  try {
    const result = marked.parse(text) as string;
    return result.trimEnd();
  } catch {
    return text;
  }
}
