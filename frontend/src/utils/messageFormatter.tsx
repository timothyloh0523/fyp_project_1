import { memo, type ReactNode } from "react";
import Markdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";

// Skip code and existing dollar-delimited math when converting LaTeX delimiters.
// Fenced code may be unfinished; preserve it through the end of the message.
const MESSAGE_TOKENS = /^[\t >]*(\x60{3,}|~{3,})[^\n]*(?:\n[\s\S]*?(?:^[\t >]*\1[\t ]*$|(?![\s\S]))|$)|(\x60+)[\s\S]*?\2(?!\x60)|(?<!\\)(\${1,2})(?!\$)[\s\S]*?(?<!\\)\3(?!\$)|\\\([\s\S]*?\\\)|\\\[[\s\S]*?\\\]/gm;

function normalizeMathDelimiters(message: string): string {
  let result = "";
  let cursor = 0;

  for (const match of message.matchAll(MESSAGE_TOKENS)) {
    let replacement = match[0];
    const inline = replacement.startsWith("\\(") ? replacement.slice(2, -2) : undefined;
    const display = replacement.startsWith("\\[") || replacement.startsWith("$$")
      ? replacement.slice(2, -2)
      : undefined;

    if (inline?.trim()) {
      replacement = "$" + inline.trim() + "$";
    } else if (display?.trim()) {
      // Keep display equations inside their surrounding list or blockquote.
      const lineStart = message.lastIndexOf("\n", match.index - 1) + 1;
      const beforeMath = message.slice(lineStart, match.index);
      const prefix = beforeMath.match(/^[\t ]*(?:>[\t ]*)*(?:(?:[-+*]|\d+[.)])[\t ]+)?/)?.[0] ?? "";
      const indent = prefix.replace(/(?:[-+*]|\d+[.)])[\t ]+$/, (marker) => " ".repeat(marker.length));
      const equation = display.trim().split("\n").map((line) => indent + line).join("\n");
      replacement = "\n" + indent + "$$\n" + equation + "\n" + indent + "$$\n" + indent;
    }

    result += message.slice(cursor, match.index) + replacement;
    cursor = match.index + match[0].length;
  }

  return result + message.slice(cursor);
}

function parseMatrix(value: string): string[][] | null {
  const source = value.trim();
  if (!source.startsWith("[") || !source.endsWith("]")) return null;

  for (const candidate of [source, source.replace(/'/g, '"')]) {
    try {
      const parsed: unknown = JSON.parse(candidate);
      if (!Array.isArray(parsed) || !parsed.length || !parsed.every(Array.isArray)) return null;
      const rows = parsed as unknown[][];
      const columns = rows[0].length;
      if (!columns || !rows.every((row) =>
        row.length === columns &&
        row.every((cell) => ["string", "number", "boolean"].includes(typeof cell))
      )) return null;
      return rows.map((row) => row.map(String));
    } catch {
      // Try the single-quoted variant; leave unrecognised input as ordinary text.
    }
  }
  return null;
}

function MessageParagraph({ children }: { children?: ReactNode }) {
  // Markdown leaves standalone nested arrays as text, including multiline arrays.
  // Recognise them here so arrays inside code blocks remain literal code.
  const rows = typeof children === "string" ? parseMatrix(children) : null;
  if (!rows) return <p>{children}</p>;

  return (
    <div className="matrix-scroll">
      <div className="matrix-wrapper">
        <table className="matrix-table" aria-label="Matrix">
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={rowIndex}>
                {row.map((cell, cellIndex) => <td key={cellIndex}>{cell}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const components: Components = {
  p: MessageParagraph,
  table: ({ children }) => (
    <div className="markdown-table">
      <table>{children}</table>
    </div>
  ),
};

type FormattedMessageProps = {
  message: string;
  className?: string;
  insideButton?: boolean;
};

// Messages don't change while typing the next question; avoid re-typesetting
// every previous equation on each keystroke.
export const FormattedMessage = memo(function FormattedMessage({
  message,
  className = "",
  insideButton = false,
}: FormattedMessageProps) {
  return (
    <div className={("formatted-message " + className).trim()}>
      <Markdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[[rehypeKatex, { trust: false, errorColor: "#f08b9d" }]]}
        components={components}
        // Answer buttons cannot contain other interactive controls.
        disallowedElements={insideButton ? ["a", "input", "button"] : undefined}
        unwrapDisallowed
        skipHtml
      >
        {normalizeMathDelimiters(message)}
      </Markdown>
    </div>
  );
});

