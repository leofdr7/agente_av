import Link from "next/link";

import { CalculationSteps } from "@/components/calculation-steps";
import { DownloadReports } from "@/components/download-reports";
import { PageHeader, Sheet } from "@/components/page-header";
import { StatusDot } from "@/components/status-dot";
import { Badge } from "@/components/ui/badge";
import type { AgentRunTrace, EstimationDetail } from "@/lib/api";
import { formatBudget, formatWhen } from "@/lib/format";
import { cn } from "cn";

type RunAlert = {
  kind: "singular" | "infeasible";
  title: string;
  detail: string;
};

export function EstimationResult({ estimation }: { estimation: EstimationDetail }) {
  const summary =
    estimation.result_json?.final_response.trim() ||
    "El agente no dejó un resumen ejecutivo en esta estimación.";
  const paragraphs = summary.split(/\n\n+/).filter(Boolean);
  const alert = runAlert(estimation.result_json);

  return (
    <>
      <PageHeader
        eyebrow={formatWhen(estimation.created_at)}
        title={estimation.project.name}
        description="Resumen de la corrida y traza de cálculo."
      />

      <dl className="mb-6 grid grid-cols-2 gap-x-4 gap-y-2 text-sm md:grid-cols-4">
        <div>
          <dt className="text-steel">Estado</dt>
          <dd>
            <StatusDot status={estimation.project.status} />
          </dd>
        </div>
        <div>
          <dt className="text-steel">Presupuesto</dt>
          <dd className="font-mono">{formatBudget(estimation.project.budget)}</dd>
        </div>
        <div className="col-span-2">
          <dt className="text-steel">Expediente</dt>
          <dd>
            <Link
              href={`/proyectos/${estimation.project_id}`}
              className="text-ink underline-offset-2 hover:underline"
            >
              Ver historial del proyecto
            </Link>
          </dd>
        </div>
      </dl>

      {alert ? <DiagnosisBanner alert={alert} /> : null}

      <Sheet className="mb-8 px-4 py-4">
        <h2 className="text-sm font-medium text-ink">Enunciado</h2>
        <p className="mt-2 whitespace-pre-wrap text-sm text-ink/90">
          {estimation.problem_text}
        </p>
      </Sheet>

      <section className="mb-8">
        <h2 className="mb-3 flex flex-wrap items-center gap-2 text-sm font-medium text-ink">
          Resumen ejecutivo
          {alert ? (
            <Badge variant="destructive" className="h-5 rounded-md">
              {alert.title}
            </Badge>
          ) : null}
        </h2>
        <div
          className={cn(
            "space-y-3 border-l-[3px] pl-3",
            alert ? "border-destructive" : "border-copper",
          )}
        >
          {paragraphs.map((paragraph) => (
            <p key={paragraph.slice(0, 24)} className="max-w-prose text-ink">
              {paragraph}
            </p>
          ))}
        </div>
      </section>

      <section className="mb-8">
        <h2 className="mb-3 text-sm font-medium text-ink">Pasos de cálculo</h2>
        {estimation.result_json ? (
          <CalculationSteps trace={estimation.result_json} />
        ) : (
          <p className="text-sm text-steel">
            Todavía no hay traza. Vuelve a abrir esta página cuando termine la
            corrida.
          </p>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-sm font-medium text-ink">Informe</h2>
        <DownloadReports
          estimationId={estimation.id}
          initialReports={estimation.reports}
        />
      </section>
    </>
  );
}

function DiagnosisBanner({ alert }: { alert: RunAlert }) {
  return (
    <div
      role="status"
      className="mb-8 border-l-[3px] border-destructive bg-destructive/10 px-3 py-3 dark:bg-destructive/20"
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="destructive" className="h-5 rounded-md">
          {alert.title}
        </Badge>
        <p className="text-sm font-medium text-ink">Diagnóstico de alerta</p>
      </div>
      <p className="mt-2 max-w-prose text-sm text-ink/90">{alert.detail}</p>
    </div>
  );
}

function runAlert(trace: AgentRunTrace | null): RunAlert | null {
  if (!trace) return null;

  const feasibility = asRecord(trace.feasibility);
  if (feasibility?.infeasible === true) {
    const reasons = Array.isArray(feasibility.reasons)
      ? feasibility.reasons.filter((item): item is string => typeof item === "string")
      : [];
    return {
      kind: "infeasible",
      title: "Plan infactible",
      detail:
        reasons[0] ??
        "El vector solución tiene componentes negativas: el plan no es realizable en planta.",
    };
  }

  for (const tool of trace.tools) {
    if (tool.name !== "diagnosticar_sistema") continue;
    const output = asRecord(tool.output);
    if (output?.is_singular !== true) continue;
    const message = typeof output.message === "string" ? output.message : "";
    const classification =
      typeof output.classification === "string"
        ? output.classification.split("_").join(" ")
        : "";
    return {
      kind: "singular",
      title: "Sistema singular",
      detail:
        message ||
        (classification
          ? `El sistema es ${classification} y no admite una solución única.`
          : "El sistema es singular: el motor no entrega un vector solución."),
    };
  }

  return null;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return null;
}
