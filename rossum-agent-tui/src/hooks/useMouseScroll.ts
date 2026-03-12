import { useEffect, useRef } from "react";
import { useStdin, useStdout } from "ink";

// SGR (1006) mouse mode escape sequences
const ENABLE_MOUSE = "\x1b[?1000h\x1b[?1006h";
const DISABLE_MOUSE = "\x1b[?1000l\x1b[?1006l";

// SGR mouse event: ESC[<button;col;row{M|m}
// eslint-disable-next-line no-control-regex
const SGR_MOUSE_RE = /\x1b\[<(\d+);(\d+);(\d+)([Mm])/;

// Button codes for scroll wheel in SGR mode
const SCROLL_UP = 64;
const SCROLL_DOWN = 65;

interface UseMouseScrollOptions {
  onScrollUp: () => void;
  onScrollDown: () => void;
  isActive?: boolean;
}

export function useMouseScroll({
  onScrollUp,
  onScrollDown,
  isActive = true,
}: UseMouseScrollOptions) {
  const { stdin } = useStdin();
  const { stdout } = useStdout();
  const callbacksRef = useRef({ onScrollUp, onScrollDown });
  callbacksRef.current = { onScrollUp, onScrollDown };

  useEffect(() => {
    if (!isActive || !stdin || !stdout) return;

    stdout.write(ENABLE_MOUSE);

    const onData = (data: Buffer) => {
      const str = data.toString("utf-8");
      const match = SGR_MOUSE_RE.exec(str);
      if (!match) return;

      const button = parseInt(match[1]!, 10);
      if (button === SCROLL_UP) {
        callbacksRef.current.onScrollUp();
      } else if (button === SCROLL_DOWN) {
        callbacksRef.current.onScrollDown();
      }
    };

    stdin.on("data", onData);
    return () => {
      stdin.off("data", onData);
      stdout.write(DISABLE_MOUSE);
    };
  }, [isActive, stdin, stdout]);
}
