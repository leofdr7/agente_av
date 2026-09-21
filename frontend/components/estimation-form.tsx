"use client";

import { useActionState, useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import { submitEstimation, type ActionState } from "@/app/(app)/actions";
import { ErrorNotice } from "@/components/error-notice";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { Project } from "@/lib/api";
import { formatBudget } from "@/lib/format";
import { cn } from "cn";

const fieldControlClass =
  "h-9 rounded-md bg-sheet focus-visible:border-copper focus-visible:ring-3 focus-visible:ring-copper/40";

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
    <Card className="rounded-md bg-sheet py-5 shadow-none ring-1 ring-ink/12 [--card-spacing:--spacing(5)] dark:ring-ink/20">
      <CardContent className="px-4 sm:px-6">
        <form
          action={action}
          className="flex flex-col gap-8"
          aria-busy={pending}
          onSubmit={(event) => {
            if (pending) event.preventDefault();
          }}
        >
          <input type="hidden" name="mode" value={mode} />
          <input type="hidden" name="budget" value={budgetSubmitValue(budget)} />

          <fieldset className="flex flex-col gap-2" disabled={pending}>
            <legend className="text-sm font-medium text-ink">Proyecto</legend>
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
              className="grid w-full min-w-0 grid-cols-2 overflow-hidden rounded-md bg-paper ring-1 ring-ink/15 focus-within:ring-2 focus-within:ring-copper dark:bg-background dark:ring-ink/25"
              aria-label="Tipo de proyecto"
            >
              <ToggleGroupItem
                value="existing"
                disabled={projects.length === 0 || pending}
                className={cn(
                  "h-9 min-w-0 flex-1 rounded-none border-0 bg-transparent px-2 text-steel hover:bg-sheet hover:text-ink",
                  "focus-visible:border-copper focus-visible:ring-3 focus-visible:ring-copper/40",
                  "aria-pressed:bg-copper aria-pressed:text-white aria-pressed:hover:bg-copper aria-pressed:hover:text-white",
                  "data-[pressed]:bg-copper data-[pressed]:text-white data-[pressed]:hover:bg-copper data-[pressed]:hover:text-white",
                )}
              >
                Existente
              </ToggleGroupItem>
              <ToggleGroupItem
                value="new"
                disabled={pending}
                className={cn(
                  "h-9 min-w-0 flex-1 rounded-none border-0 bg-transparent px-2 text-steel hover:bg-sheet hover:text-ink",
                  "focus-visible:border-copper focus-visible:ring-3 focus-visible:ring-copper/40",
                  "aria-pressed:bg-copper aria-pressed:text-white aria-pressed:hover:bg-copper aria-pressed:hover:text-white",
                  "data-[pressed]:bg-copper data-[pressed]:text-white data-[pressed]:hover:bg-copper data-[pressed]:hover:text-white",
                )}
              >
                Nuevo
              </ToggleGroupItem>
            </ToggleGroup>

            {mode === "existing" ? (
              <div className="flex flex-col gap-1">
                <Label htmlFor="project_id" className="text-ink">
                  Cuál
                </Label>
                <select
                  id="project_id"
                  name="project_id"
                  value={projectId}
                  onChange={(event) => chooseProject(event.target.value)}
                  required
                  disabled={pending}
                  className={cn(
                    "w-full border border-input px-2.5 text-base outline-none disabled:opacity-60 md:text-sm",
                    fieldControlClass,
                  )}
                >
                  {projects.map((project) => (
                    <option key={project.id} value={project.id}>
                      {project.name}
                      {project.budget != null ? ` · ${formatBudget(project.budget)}` : ""}
                    </option>
                  ))}
                </select>
              </div>
            ) : (
              <div className="flex flex-col gap-1">
                <Label htmlFor="project_name" className="text-ink">
                  Nombre
                </Label>
                <Input
                  id="project_name"
                  name="project_name"
                  required
                  maxLength={200}
                  placeholder="Línea AI-Edge, turno noche"
                  disabled={pending}
                  className={fieldControlClass}
                />
              </div>
            )}
          </fieldset>

          <div className="flex flex-col gap-1">
            <Label htmlFor="budget" className="text-ink">
              Presupuesto asociado
            </Label>
            <div
              className={cn(
                "flex h-9 min-w-0 items-center rounded-md border border-input bg-sheet",
                "focus-within:border-copper focus-within:ring-3 focus-within:ring-copper/40",
                pending && "opacity-50",
              )}
            >
              <span
                aria-hidden
                className="shrink-0 pl-2.5 pr-1 font-mono text-sm text-steel"
              >
                $
              </span>
              <Input
                id="budget"
                inputMode="decimal"
                value={formatBudgetDisplay(budget)}
                onChange={(event) => setBudget(sanitizeBudgetInput(event.target.value))}
                placeholder="120,000"
                disabled={pending}
                aria-describedby="budget-help"
                className="h-full min-w-0 flex-1 rounded-md border-0 bg-transparent px-0 font-mono shadow-none focus-visible:border-transparent focus-visible:ring-0 disabled:bg-transparent dark:bg-transparent"
              />
            </div>
            <p id="budget-help" className="text-xs text-steel">
              Queda guardado en el proyecto, en dólares.
            </p>
          </div>

          <div className="flex flex-col gap-1">
            <Label htmlFor="problem_text" className="text-ink">
              Problema vectorial
            </Label>
            <Textarea
              id="problem_text"
              name="problem_text"
              required
              minLength={8}
              rows={8}
              placeholder="¿Qué plan de producción es viable con el inventario actual?"
              disabled={pending}
              aria-describedby="problem-help"
              className="min-h-40 rounded-md bg-sheet focus-visible:border-copper focus-visible:ring-3 focus-visible:ring-copper/40"
            />
            <p id="problem-help" className="text-xs text-steel">
              El agente interpreta lenguaje natural; no hace falta escribir solo números.
            </p>
          </div>

          {state?.error ? (
            <ErrorNotice title="No se pudo generar la estimación">
              {state.error}
            </ErrorNotice>
          ) : null}

          {pending ? (
            <p
              className="border-l-[3px] border-copper bg-paper px-3 py-2 text-sm text-ink dark:bg-background"
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
            className="h-10 w-full max-w-full gap-2 whitespace-nowrap md:w-auto"
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
        </form>
      </CardContent>
    </Card>
  );
}
