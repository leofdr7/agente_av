"use client";

import { useActionState, useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import { submitEstimation, type ActionState } from "@/app/(app)/actions";
import { ErrorNotice } from "@/components/error-notice";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { Project } from "@/lib/api";
import { formatBudget } from "@/lib/format";
import { cn } from "cn";
import "./form-design.css";

const fieldControlClass = "estimation-control";

function budgetText(project: Project | undefined): string {
  return project?.budget != null ? String(project.budget) : "";
}

function sanitizeBudgetInput(raw: string): string {
  const stripped = raw.replace(/[^\d.]/g, "");
  if (!stripped) return "";
  const firstDot = stripped.indexOf(".");
  if (firstDot === -1) {
    return stripped.replace(/^0+(?=\d)/, "");
  }
  const intPart = (stripped.slice(0, firstDot).replace(/^0+(?=\d)/, "") || "0");
  const decPart = stripped.slice(firstDot + 1).replace(/\./g, "").slice(0, 2);
  if (stripped.endsWith(".") && decPart === "") {
    return `${intPart}.`;
  }
  return `${intPart}.${decPart}`;
}

function formatBudgetDisplay(raw: string): string {
  if (!raw) return "";
  const endsWithDot = raw.endsWith(".");
  const [intPart, decPart] = raw.split(".");
  const grouped = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  if (endsWithDot) return `${grouped}.`;
  if (decPart !== undefined) return `${grouped}.${decPart}`;
  return grouped;
}

function budgetSubmitValue(raw: string): string {
  if (!raw || raw === ".") return "";
  return raw.endsWith(".") ? raw.slice(0, -1) : raw;
}

export function EstimationForm({ projects }: { projects: Project[] }) {
  const [state, action, pending] = useActionState(
    submitEstimation,
    null as ActionState,
  );
  const [mode, setMode] = useState<"existing" | "new">(
    projects.length > 0 ? "existing" : "new",
  );
  const [projectId, setProjectId] = useState(projects[0]?.id ?? "");
  const [budget, setBudget] = useState(budgetText(projects[0]));

  useEffect(() => {
    if (state?.error && !pending) {
      toast.error("No se pudo generar la estimación", {
        description: state.error,
      });
    }
  }, [state, pending]);

  const chooseMode = (next: "existing" | "new") => {
    setMode(next);
    if (next === "existing") {
      setBudget(budgetText(projects.find((project) => project.id === projectId)));
    }
  };

  const chooseProject = (id: string) => {
    setProjectId(id);
    setBudget(budgetText(projects.find((project) => project.id === id)));
  };

  return (
    <form
      action={action}
      className="estimation-form"
      aria-busy={pending}
      onSubmit={(event) => {
        if (pending) event.preventDefault();
      }}
    >
      <input type="hidden" name="mode" value={mode} />
      <input type="hidden" name="budget" value={budgetSubmitValue(budget)} />

      <div className="estimation-context">
        <fieldset className="estimation-project" disabled={pending}>
          <legend className="estimation-label">Proyecto</legend>
          <ToggleGroup
            value={[mode]}
            onValueChange={(next) => {
              const value = next[0];
              if (value === "existing" || value === "new") {
                chooseMode(value);
              }
            }}
            disabled={pending}
            spacing={0}
            className="estimation-mode"
            aria-label="Tipo de proyecto"
          >
            <ToggleGroupItem
              value="existing"
              disabled={projects.length === 0 || pending}
              className="estimation-mode-option"
            >
              Existente
            </ToggleGroupItem>
            <ToggleGroupItem
              value="new"
              disabled={pending}
              className="estimation-mode-option"
            >
              Nuevo
            </ToggleGroupItem>
          </ToggleGroup>

          {mode === "existing" ? (
            <div className="estimation-field">
              <Label htmlFor="project_id" className="estimation-label">
                Cuál
              </Label>
              <select
                id="project_id"
                name="project_id"
                value={projectId}
                onChange={(event) => chooseProject(event.target.value)}
                required
                disabled={pending}
                className={fieldControlClass}
              >
                {projects.map((project) => (
                  <option key={project.id} value={project.id}>
                    {project.name}
                    {project.budget != null ? ` (${formatBudget(project.budget)})` : ""}
                  </option>
                ))}
              </select>
            </div>
          ) : (
            <div className="estimation-field">
              <Label htmlFor="project_name" className="estimation-label">
                Nombre
              </Label>
              <Input
                id="project_name"
                name="project_name"
                required
                maxLength={200}
                placeholder="Nombre del proyecto o lote a evaluar"
                disabled={pending}
                className={fieldControlClass}
              />
            </div>
          )}
        </fieldset>

        <div className="estimation-field estimation-budget">
          <Label htmlFor="budget" className="estimation-label">
            Presupuesto asociado
          </Label>
          <div
            className={cn(
              "estimation-budget-control",
              pending && "opacity-50",
            )}
          >
            <span
              aria-hidden
              className="estimation-currency"
            >
              $
            </span>
            <Input
              id="budget"
              inputMode="decimal"
              value={formatBudgetDisplay(budget)}
              onChange={(event) => setBudget(sanitizeBudgetInput(event.target.value))}
              placeholder="Monto disponible, $"
              disabled={pending}
              aria-describedby="budget-help"
              className="estimation-budget-input"
            />
          </div>
          <p id="budget-help" className="estimation-help">
            Queda guardado en el proyecto, en dólares.
          </p>
        </div>
      </div>

      <div className="estimation-field estimation-problem">
        <Label htmlFor="problem_text" className="estimation-label">
          Problema vectorial
        </Label>
        <Textarea
          id="problem_text"
          name="problem_text"
          required
          minLength={8}
          rows={8}
          placeholder="Describe el sistema: qué variables intervienen, qué restricciones tienes y qué necesitas resolver. AgentA extrae las ecuaciones automáticamente por ti..."
          disabled={pending}
          aria-describedby="problem-help"
          className="estimation-problem-input"
        />
        <p id="problem-help" className="estimation-help">
          El agente interpreta lenguaje natural; no hace falta escribir solo números.
        </p>
      </div>

      <div className="estimation-submit-area">
        {state?.error ? (
          <ErrorNotice title="No se pudo generar la estimación">
            {state.error}
          </ErrorNotice>
        ) : null}

        {pending ? (
          <p
            className="estimation-pending"
            aria-live="polite"
            role="status"
          >
            El agente está diagnosticando y resolviendo el sistema. Puede tardar
            cerca de un minuto.
          </p>
        ) : null}

        <Button
          type="submit"
          disabled={pending}
          className="estimation-submit"
        >
          {pending ? (
            <>
              <Loader2 className="size-4 animate-spin" aria-hidden />
              Calculando...
            </>
          ) : (
            "Enviar al agente"
          )}
        </Button>
      </div>
    </form>
  );
}
