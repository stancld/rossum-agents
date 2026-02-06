import { useState, useEffect } from "react";
import { useStdout } from "ink";

export function useTerminalSize() {
  const { stdout } = useStdout();
  const [size, setSize] = useState({
    rows: stdout?.rows ?? 24,
    columns: stdout?.columns ?? 80,
  });

  useEffect(() => {
    if (!stdout) return;

    const onResize = () => {
      setSize({ rows: stdout.rows, columns: stdout.columns });
    };

    stdout.on("resize", onResize);
    return () => {
      stdout.off("resize", onResize);
    };
  }, [stdout]);

  return size;
}
