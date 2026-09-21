import type { AgentRunTrace, ToolCallRecord } from "@/lib/api";
import { cn } from "cn";

const TOOL_TITLE: Record<string, string> = {
  buscar_conocimiento: "Consulta al vault",
  diagnosticar_sistema: "Diagnóstico del sistema",
  resolver_por_gauss: "Eliminación de Gauss",
  resolver_por_gauss_jordan: "Gauss-Jordan",
  resolver_por_matriz_inversa: "Matriz inversa",
};

// Los tres métodos aplican las mismas operaciones de fila (el pivoteo solo mira A),
// pero trabajan sobre matrices distintas. Decir cuál es evita leerlos como repetidos.
const WORKING_MATRIX: Record<string, string> = {
  resolver_por_gauss:
    "Matriz ampliada [A|B] triangulada por debajo del pivote; X sale por sustitución hacia atrás.",
  resolver_por_gauss_jordan:
    "Matriz ampliada [A|B] reducida hasta [I|X]: la última columna termina siendo el vector solución.",
  resolver_por_matriz_inversa:
    "Matriz ampliada [A|I] reducida hasta [I|A⁻¹]: el bloque derecho termina siendo la inversa.",
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
            <summary className="flex cursor-pointer list-none items-baseline gap-3 px-1 py-3 marker:content-none [&::-webkit-details-marker]:hidden">
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
              <StepCount tool={tool} />
            </summary>
            <div className="pb-6 pl-10 pr-1 text-sm text-ink/90">
              <ToolBody tool={tool} />
            </div>
          </details>
        </li>
      ))}
    </ol>
  );
}

function StepCount({ tool }: { tool: ToolCallRecord }) {
  const steps = asRecord(tool.output)?.steps;
  if (!Array.isArray(steps) || steps.length === 0) return null;
  return (
    <span className="font-mono text-[11px] text-steel">
      {steps.length} {steps.length === 1 ? "operación" : "operaciones"}
    </span>
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
      <div className="space-y-3">
        <dl className="grid max-w-md grid-cols-[auto_1fr] gap-x-6 gap-y-2">
          <Row label="clasificación" value={classification(output.classification)} />
          <Row label="det(A)" value={str(output.determinant)} />
          <Row label="rango(A)" value={str(output.rank_a)} />
          <Row label="rango([A|B])" value={str(output.rank_augmented)} />
        </dl>
        {typeof output.message === "string" ? (
          <p className="max-w-prose leading-relaxed text-steel">{output.message}</p>
        ) : null}
      </div>
    );
  }

  const solution = output.solution;
  const steps = Array.isArray(output.steps) ? output.steps : [];
  const diagnosis = asRecord(output.diagnostico) ?? asRecord(output.diagnosis);
  const inverse = asMatrix(output.inverse_matrix);
  const components = Array.isArray(output.component_steps)
    ? output.component_steps
    : [];
  const caption = WORKING_MATRIX[tool.name];
  const size = Array.isArray(solution) ? solution.length : undefined;

  return (
    <div className="space-y-5">
      {diagnosis && typeof diagnosis.message === "string" ? (
        <p className="max-w-prose leading-relaxed text-steel">{diagnosis.message}</p>
      ) : null}

      {Array.isArray(solution) ? (
        <div className="border-l-[3px] border-copper pl-3">
          <p className="text-[11px] text-steel">Vector solución</p>
          <p className="mt-0.5 font-mono tabular-nums text-ink">
            X = ({solution.map((value) => formatNumber(value)).join(", ")})
          </p>
        </div>
      ) : null}

      {caption && steps.length > 0 ? (
        <p className="max-w-prose text-xs leading-relaxed text-steel">{caption}</p>
      ) : null}

      {steps.length > 0 ? (
        <ol className="space-y-4">
          {steps.map((step, index) => {
            const record = asRecord(step);
            const description =
              record && typeof record.description === "string"
                ? record.description
                : stringify(step);
            return (
              <li key={index} className="space-y-1.5">
                <div className="flex items-baseline gap-2">
                  <span className="font-mono text-[11px] text-steel">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <span className="font-medium text-ink">{description}</span>
                </div>
                <Matrix matrix={asMatrix(record?.matrix_state)} split={size} />
              </li>
            );
          })}
        </ol>
      ) : null}

      {inverse ? (
        <div className="space-y-1.5">
          <p className="font-medium text-ink">Matriz inversa A⁻¹</p>
          <Matrix matrix={inverse} />
        </div>
      ) : null}

      {components.length > 0 ? (
        <div className="space-y-1.5">
          <p className="font-medium text-ink">Despeje de las componentes de X</p>
          <ul className="space-y-1 font-mono text-xs tabular-nums text-steel">
            {components.map((item, index) => {
              const record = asRecord(item);
              if (!record) return null;
              return (
                <li key={index}>
                  {str(record.equation)}
                  <span className="text-ink"> = {str(record.value)}</span>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}

      {!solution && steps.length === 0 ? (
        <pre className="overflow-x-auto font-mono text-xs whitespace-pre-wrap text-steel">
          {stringify(tool.output)}
        </pre>
      ) : null}
    </div>
  );
}

/** Estado de la matriz de trabajo. `split` marca la barra de ampliación. */
function Matrix({
  matrix,
  split,
}: {
  matrix: number[][] | null;
  split?: number;
}) {
  if (!matrix) return null;
  const bar = split && matrix[0] && split < matrix[0].length ? split : null;

  return (
    <div className="overflow-x-auto">
      <table className="border-y border-ink/15 font-mono text-xs tabular-nums">
        <tbody>
          {matrix.map((row, i) => (
            <tr key={i} className="border-b border-ink/10 last:border-0">
              {row.map((value, j) => (
                <td
                  key={j}
                  className={cn(
                    "px-2 py-1 text-right text-ink/90",
                    j === bar && "border-l border-ink/30",
                  )}
                >
                  {formatNumber(value)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  if (!value) return null;
  return (
    <>
      <dt className="text-steel">{label}</dt>
      <dd className="font-mono tabular-nums">{value}</dd>
    </>
  );
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return null;
}

function asMatrix(value: unknown): number[][] | null {
  if (!Array.isArray(value) || value.length === 0) return null;
  if (!value.every((row) => Array.isArray(row))) return null;
  return value as number[][];
}

function classification(value: unknown): string {
  if (typeof value !== "string") return str(value);
  return value.split("_").join(" ");
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
