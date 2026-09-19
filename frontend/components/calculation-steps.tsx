import type { AgentRunTrace, ToolCallRecord } from "@/lib/api";

const TOOL_TITLE: Record<string, string> = {
  buscar_conocimiento: "Consulta al vault",
  diagnosticar_sistema: "Diagnóstico del sistema",
  resolver_por_gauss: "Eliminación de Gauss",
  resolver_por_gauss_jordan: "Gauss-Jordan",
  resolver_por_matriz_inversa: "Matriz inversa",
};

export function CalculationSteps({ trace }: { trace: AgentRunTrace }) {
  if (!trace.tools.length) {
    return (
      <p className="text-sm text-steel">
        Esta corrida no dejó pasos de cálculo en la traza.
      </p>
    );
  }

  return (
    <ol className="divide-y divide-ink/10 border-y border-ink/10">
      {trace.tools.map((tool, index) => (
        <li key={`${tool.name}-${index}`}>
          <details className="group">
            <summary className="flex cursor-pointer list-none items-start gap-3 px-1 py-3 marker:content-none [&::-webkit-details-marker]:hidden">
              <span className="font-mono text-sm text-copper">
                {String(index + 1).padStart(2, "0")}
              </span>
              <span className="flex-1 text-sm font-medium text-ink">
                {TOOL_TITLE[tool.name] ?? tool.name}
                {tool.is_error ? (
                  <span className="ml-2 font-normal text-destructive">
                    no completó
                  </span>
                ) : null}
              </span>
            </summary>
            <div className="pb-4 pl-10 pr-1 text-sm text-ink/90">
              <ToolBody tool={tool} />
            </div>
          </details>
        </li>
      ))}
    </ol>
  );
}

function ToolBody({ tool }: { tool: ToolCallRecord }) {
  const output = asRecord(tool.output);
  if (!output) {
    return (
      <pre className="overflow-x-auto font-mono text-xs whitespace-pre-wrap">
        {stringify(tool.output)}
      </pre>
    );
  }

  if (tool.name === "diagnosticar_sistema") {
    return (
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
        <Row label="clasificación" value={str(output.classification)} />
        <Row label="det(A)" value={str(output.determinant)} />
        <Row label="rango(A)" value={str(output.rank_a)} />
        <Row label="rango([A|B])" value={str(output.rank_augmented)} />
        {typeof output.message === "string" ? (
          <div className="col-span-2 mt-2 text-steel">{output.message}</div>
        ) : null}
      </dl>
    );
  }

  const solution = output.solution;
  const steps = Array.isArray(output.steps) ? output.steps : [];
  const diagnosis = asRecord(output.diagnostico) ?? asRecord(output.diagnosis);

  return (
    <div className="space-y-3">
      {diagnosis && typeof diagnosis.message === "string" ? (
        <p className="text-steel">{diagnosis.message}</p>
      ) : null}
      {Array.isArray(solution) ? (
        <p>
          <span className="text-steel">X = </span>
          <span className="font-mono">
            [{solution.map((value) => formatNumber(value)).join(", ")}]
          </span>
        </p>
      ) : null}
      {steps.length > 0 ? (
        <ol className="space-y-1 font-mono text-xs text-steel">
          {steps.map((step, index) => {
            const record = asRecord(step);
            const description =
              (record && typeof record.description === "string"
                ? record.description
                : stringify(step)) ?? "";
            return (
              <li key={index}>
                {index + 1}. {description}
              </li>
            );
          })}
        </ol>
      ) : null}
      {!solution && steps.length === 0 ? (
        <pre className="overflow-x-auto font-mono text-xs whitespace-pre-wrap text-steel">
          {stringify(tool.output)}
        </pre>
      ) : null}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  if (!value) return null;
  return (
    <>
      <dt className="text-steel">{label}</dt>
      <dd className="font-mono">{value}</dd>
    </>
  );
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return null;
}

function str(value: unknown): string {
  if (value == null) return "";
  if (typeof value === "number") return formatNumber(value);
  return String(value);
}

function formatNumber(value: unknown): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return String(value ?? "");
  }
  if (Number.isInteger(value)) return String(value);
  return value.toPrecision(6).replace(/\.?0+$/, "");
}

function stringify(value: unknown): string {
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}
