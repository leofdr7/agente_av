import Markdown from "react-markdown";
import type { Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import { cn } from "cn";

// El agente redacta el resumen en Markdown (GFM). Cada elemento se mapea al
// sistema de diseño en vez de heredar los estilos del navegador.
const COMPONENTS: Components = {
  h1: ({ children }) => (
    <h3 className="mt-6 text-base font-semibold text-ink">{children}</h3>
  ),
  h2: ({ children }) => (
    <h4 className="mt-6 border-b border-ink/10 pb-1 text-sm font-semibold text-ink">
      {children}
    </h4>
  ),
  h3: ({ children }) => (
    <h5 className="mt-5 text-sm font-medium text-ink">{children}</h5>
  ),
  h4: ({ children }) => (
    <h6 className="mt-4 text-sm font-medium text-steel">{children}</h6>
  ),
  p: ({ children }) => (
    <p className="mt-3 max-w-prose leading-relaxed text-ink/90">{children}</p>
  ),
  strong: ({ children }) => (
    <strong className="font-semibold text-ink">{children}</strong>
  ),
  em: ({ children }) => <em className="italic">{children}</em>,
  ul: ({ children }) => (
    <ul className="mt-3 max-w-prose list-disc space-y-1 pl-5 text-ink/90">
      {children}
    </ul>
  ),
  ol: ({ children }) => (
    <ol className="mt-3 max-w-prose list-decimal space-y-1 pl-5 text-ink/90">
      {children}
    </ol>
  ),
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  blockquote: ({ children }) => (
    <blockquote className="mt-3 border-l-2 border-ink/20 pl-3 text-steel">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="mt-5 border-ink/10" />,
  a: ({ children, href }) => (
    <a href={href} className="text-ink underline underline-offset-2">
      {children}
    </a>
  ),
  table: ({ children }) => (
    <div className="mt-4 overflow-x-auto">
      <table className="w-full border-y border-ink/15 text-sm tabular-nums">
        {children}
      </table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="border-b border-ink/15">{children}</thead>
  ),
  tr: ({ children }) => (
    <tr className="border-b border-ink/10 last:border-0">{children}</tr>
  ),
  th: ({ children, style }) => (
    <th
      style={style}
      className="px-2 py-1.5 text-left align-bottom font-medium text-steel"
    >
      {children}
    </th>
  ),
  td: ({ children, style }) => (
    <td style={style} className="px-2 py-1.5 align-top text-ink/90">
      {children}
    </td>
  ),
  code: ({ children, className }) => {
    // Los bloques ``` llegan con `language-*`; el código en línea, sin clase.
    if (className) {
      return <code className="font-mono text-xs leading-relaxed">{children}</code>;
    }
    return (
      <code className="bg-paper px-1 py-0.5 font-mono text-[0.85em] text-ink dark:bg-background">
        {children}
      </code>
    );
  },
  pre: ({ children }) => (
    <pre className="mt-4 overflow-x-auto bg-paper px-3 py-2 font-mono text-xs text-ink dark:bg-background">
      {children}
    </pre>
  ),
};

export function MarkdownSummary({
  children,
  className,
}: {
  children: string;
  className?: string;
}) {
  return (
    <div className={cn("[&>*:first-child]:mt-0", className)}>
      <Markdown remarkPlugins={[remarkGfm]} components={COMPONENTS}>
        {children}
      </Markdown>
    </div>
  );
}
