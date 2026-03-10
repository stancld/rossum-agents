import { Marked, type MarkedExtension, type Token } from "marked";
import { markedTerminal } from "marked-terminal";

interface TerminalRendererExtension extends MarkedExtension {
  renderer?: {
    text?: (token: Token) => string;
  };
}

function hasInlineTokens(token: Token): token is Token & { tokens: Token[] } {
  return "tokens" in token && Array.isArray(token.tokens);
}

// Single-entry cache: terminal width rarely changes, so we only keep the last
// instance and rebuild when the width differs.
let cachedWidth = 0;
let cachedMarked: Marked | null = null;

function getMarked(width: number): Marked {
  if (cachedMarked && cachedWidth === width) return cachedMarked;

  const instance = new Marked();

  // markedTerminal() returns a MarkedExtension at runtime, but @types declares
  // TerminalRenderer. We also patch `text` rendering so inline tokens nested in
  // list-item text (e.g. markdown links) are rendered instead of printed raw.
  const terminalExtension = markedTerminal({
    width,
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
  instance.use(terminalExtension as MarkedExtension);

  cachedWidth = width;
  cachedMarked = instance;
  return instance;
}

export function renderMarkdown(text: string, width: number): string {
  try {
    const result = getMarked(width).parse(text) as string;
    return result.trimEnd();
  } catch {
    return text;
  }
}
