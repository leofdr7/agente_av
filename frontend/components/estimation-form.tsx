"use client";

import { useActionState, useEffect, useState, type ReactNode } from "react";
import { toast } from "sonner";

import { submitEstimation, type ActionState } from "@/app/(app)/actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { Project } from "@/lib/api";
import { formatBudget } from "@/lib/format";
import { cn } from "cn";

function budgetText(project: Project | undefined): string {
  return project?.budget != null ? String(project.budget) : "";
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
      toast.error(state.error);
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
    <form action={action} className="relative space-y-6">
      <input type="hidden" name="mode" value={mode} />

      <fieldset className="space-y-3">
        <legend className="text-sm font-medium text-ink">Proyecto</legend>
        <div className="grid grid-cols-2 gap-px bg-ink/15 ring-1 ring-ink/15">
          <ModeButton
            current={mode}
            value="existing"
            disabled={projects.length === 0}
            onSelect={chooseMode}
          >
            Existente
          </ModeButton>
          <ModeButton current={mode} value="new" onSelect={chooseMode}>
            Nuevo
          </ModeButton>
        </div>

        {mode === "existing" ? (
          <div className="space-y-1.5">
            <Label htmlFor="project_id">Cuál</Label>
            <select
              id="project_id"
              name="project_id"
              value={projectId}
              onChange={(event) => chooseProject(event.target.value)}
              required
              className="h-9 w-full rounded-md border border-input bg-sheet px-2.5 text-base md:text-sm"
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
          <div className="space-y-1.5">
            <Label htmlFor="project_name">Nombre</Label>
            <Input
              id="project_name"
              name="project_name"
              required
              maxLength={200}
              placeholder="Línea AI-Edge, turno noche"
              className="h-9 bg-sheet"
            />
          </div>
        )}
      </fieldset>

      <div className="space-y-1.5">
        <Label htmlFor="budget">Presupuesto asociado</Label>
        <Input
          id="budget"
          name="budget"
          inputMode="decimal"
          value={budget}
          onChange={(event) => setBudget(event.target.value)}
          placeholder="120000"
          className="h-9 bg-sheet font-mono"
        />
        <p className="text-xs text-steel">
          Queda guardado en el proyecto, en dólares.
        </p>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="problem_text">Problema vectorial</Label>
        <Textarea
          id="problem_text"
          name="problem_text"
          required
          minLength={8}
          rows={8}
          placeholder="Nos quedamos cortos de resina de encapsulado. ¿Qué plan de producción es viable con el inventario actual?"
          className="min-h-40 bg-sheet"
        />
      </div>

      {state?.error ? (
        <p className="text-sm text-destructive" role="alert">
          {state.error}
        </p>
      ) : null}

      <Button type="submit" disabled={pending} className="h-10 w-full md:w-auto">
        {pending ? "Resolviendo…" : "Enviar al agente"}
      </Button>

      {pending ? (
        <div
          className="absolute inset-0 flex items-end bg-paper/70 p-4 backdrop-blur-[1px] sm:items-center sm:justify-center"
          aria-live="polite"
        >
          <p className="max-w-sm border-l-[3px] border-copper bg-sheet px-3 py-2 text-sm text-ink shadow-sm">
            El agente está diagnosticando y resolviendo el sistema. Puede tardar
            cerca de un minuto.
          </p>
        </div>
      ) : null}
    </form>
  );
}

function ModeButton({
  current,
  value,
  onSelect,
  disabled,
  children,
}: {
  current: "existing" | "new";
  value: "existing" | "new";
  onSelect: (value: "existing" | "new") => void;
  disabled?: boolean;
  children: ReactNode;
}) {
  const active = current === value;
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => onSelect(value)}
      className={cn(
        "h-9 bg-sheet text-sm disabled:opacity-40",
        active ? "text-ink ring-1 ring-copper" : "text-steel",
      )}
    >
      {children}
    </button>
  );
}
