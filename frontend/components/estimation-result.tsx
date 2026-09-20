import Link from "next/link";

import { CalculationSteps } from "@/components/calculation-steps";
import { DownloadReports } from "@/components/download-reports";
import { PageHeader, Sheet } from "@/components/page-header";
import { StatusDot } from "@/components/status-dot";
import type { EstimationDetail } from "@/lib/api";
import { formatBudget, formatWhen } from "@/lib/format";

export function EstimationResult({ estimation }: { estimation: EstimationDetail }) {
  const summary =
    estimation.result_json?.final_response.trim() ||
    "El agente no dejó un resumen ejecutivo en esta estimación.";
  const paragraphs = summary.split(/\n\n+/).filter(Boolean);

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

      <Sheet className="mb-8 px-4 py-4">
        <h2 className="text-sm font-medium text-ink">Enunciado</h2>
        <p className="mt-2 whitespace-pre-wrap text-sm text-ink/90">
          {estimation.problem_text}
        </p>
      </Sheet>

      <section className="mb-8">
        <h2 className="mb-3 text-sm font-medium text-ink">Resumen ejecutivo</h2>
        <div className="space-y-3 border-l-[3px] border-copper pl-3">
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
