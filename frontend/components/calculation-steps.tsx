import type { AgentRunTrace, ToolCallRecord } from "@/lib/api";
import { BookOpen, Brackets, ChevronDown, Rows3, ScanLine, Sigma } from "lucide-react";
import { cn } from "cn";
import "./calculation-design.css";

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
      <p className="calculation-empty">
        Esta corrida no dejó pasos de cálculo en la traza.
      </p>
    );
  }

  return (
    <ol className="calculation-tools">
      {trace.tools.map((tool, index) => (
        <li key={`${tool.name}-${index}`} data-tool={tool.name}>
          <details className="calculation-panel">
            <summary className="calculation-summary">
              <span className="calculation-tool-symbol" aria-hidden="true">
                <ToolSymbol name={tool.name} />
              </span>
              <span className="calculation-tool-title">
                {TOOL_TITLE[tool.name] ?? tool.name}
                {tool.is_error ? (
                  <span className="calculation-tool-error">
                    no completó
                  </span>
                ) : null}
              </span>
              <StepCount tool={tool} />
              <ChevronDown className="calculation-chevron" aria-hidden="true" />
            </summary>
            <div className="calculation-body">
              <ToolBody tool={tool} />
            </div>
          </details>
        </li>
      ))}
    </ol>
  );
}

function ToolSymbol({ name }: { name: string }) {
  const symbols = {
    buscar_conocimiento: BookOpen,
    diagnosticar_sistema: ScanLine,
    resolver_por_gauss: Sigma,
    resolver_por_gauss_jordan: Rows3,
    resolver_por_matriz_inversa: Brackets,
  };
  const Symbol = symbols[name as keyof typeof symbols] ?? Brackets;
  return <Symbol />;
}

function StepCount({ tool }: { tool: ToolCallRecord }) {
  const steps = asRecord(tool.output)?.steps;
  if (!Array.isArray(steps) || steps.length === 0) return null;
  return (
    <span className="calculation-count">
      {steps.length} {steps.length === 1 ? "operación" : "operaciones"}
    </span>
  );
}

function ToolBody({ tool }: { tool: ToolCallRecord }) {
  const output = asRecord(tool.output);
  if (!output) {
    return (
      <pre className="calculation-raw">
        {stringify(tool.output)}
      </pre>
    );
  }

  if (tool.name === "diagnosticar_sistema") {
    return (
      <div className="calculation-diagnosis">
        <dl className="calculation-diagnostic-values">
          <Row label="clasificación" value={classification(output.classification)} />
          <Row label="det(A)" value={str(output.determinant)} />
          <Row label="rango(A)" value={str(output.rank_a)} />
          <Row label="rango([A|B])" value={str(output.rank_augmented)} />
        </dl>
        {typeof output.message === "string" ? (
          <p className="calculation-note">{output.message}</p>
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
    <div className="calculation-method">
      {diagnosis && typeof diagnosis.message === "string" ? (
        <p className="calculation-note">{diagnosis.message}</p>
      ) : null}

      {Array.isArray(solution) ? (
        <div className="calculation-solution">
          <p className="calculation-solution-label">Vector solución</p>
          <p className="calculation-vector font-mono">
            X = ({solution.map((value) => formatNumber(value)).join(", ")})
          </p>
        </div>
      ) : null}

      {caption && steps.length > 0 ? (
        <p className="calculation-caption">{caption}</p>
      ) : null}

      {steps.length > 0 ? (
        <ol className="calculation-operations">
          {steps.map((step, index) => {
            const record = asRecord(step);
            const description =
              record && typeof record.description === "string"
                ? record.description
                : stringify(step);
            return (
              <li key={index} className="calculation-operation">
                <div className="calculation-operation-heading">
                  <span className="calculation-operation-number">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <span className="calculation-operation-description">{description}</span>
                </div>
                <Matrix matrix={asMatrix(record?.matrix_state)} split={size} />
              </li>
            );
          })}
        </ol>
      ) : null}

      {inverse ? (
        <div className="calculation-inverse">
          <p className="calculation-subheading">Matriz inversa A⁻¹</p>
          <Matrix matrix={inverse} />
        </div>
      ) : null}

      {components.length > 0 ? (
        <div className="calculation-components">
          <p className="calculation-subheading">Despeje de las componentes de X</p>
          <ul className="calculation-equations font-mono">
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
        <pre className="calculation-raw">
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
    <div
      className="calculation-matrix-scroll"
      tabIndex={0}
      role="region"
      aria-label="Matriz de trabajo, desplazable horizontalmente"
    >
      <div className="calculation-matrix-brackets">
        <table className="calculation-matrix font-mono" aria-label="Matriz de trabajo">
          <tbody>
            {matrix.map((row, i) => (
              <tr key={i}>
                {row.map((value, j) => (
                  <td
                    key={j}
                    className={cn(
                      "calculation-matrix-value",
                      j === bar && "calculation-matrix-split",
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
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  if (!value) return null;
  return (
    <>
      <dt className="calculation-diagnostic-label">{label}</dt>
      <dd className="calculation-diagnostic-value">{value}</dd>
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
