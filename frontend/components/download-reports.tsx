"use client";

import { useState, useTransition } from "react";
import { toast } from "sonner";

import { generateReport } from "@/app/(app)/actions";
import { ErrorNotice } from "@/components/error-notice";
import { Button } from "@/components/ui/button";
import type { ReportFile } from "@/lib/api";

export function DownloadReports({
  estimationId,
  initialReports = [],
}: {
  estimationId: string;
  initialReports?: ReportFile[];
}) {
  const [reports, setReports] = useState<ReportFile[]>(initialReports);
  const [pending, start] = useTransition();
  const [busy, setBusy] = useState<"pdf" | "docx" | null>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const download = (type: "pdf" | "docx") => {
    start(async () => {
      setBusy(type);
      setError(null);
      try {
        let files = reports;
        const existing = files.find((item) => item.file_type === type);
        if (!existing) {
          setGenerating(true);
          const result = await generateReport(estimationId);
          if (!result.ok) {
            setError(result.error);
            toast.error(result.error);
            return;
          }
          files = result.reports;
          setReports(files);
        }
        const file = files.find((item) => item.file_type === type);
        if (!file) {
          const missing = "El informe no incluyó ese formato.";
          setError(missing);
          toast.error(missing);
          return;
        }
        window.location.href = file.file_url;
      } finally {
        setGenerating(false);
        setBusy(null);
      }
    });
  };

  const label = (type: "pdf" | "docx", idle: string) => {
    if (busy !== type) return idle;
    return generating ? `Generando ${type.toUpperCase()}…` : `Descargando ${type.toUpperCase()}…`;
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-2 sm:flex-row">
        <Button
          type="button"
          variant="outline"
          className="h-10 bg-sheet"
          disabled={pending}
          onClick={() => download("pdf")}
        >
          {label("pdf", "Descargar PDF")}
        </Button>
        <Button
          type="button"
          variant="outline"
          className="h-10 bg-sheet"
          disabled={pending}
          onClick={() => download("docx")}
        >
          {label("docx", "Descargar DOCX")}
        </Button>
      </div>
      {error ? (
        <ErrorNotice title="No se pudo generar el informe">{error}</ErrorNotice>
      ) : null}
    </div>
  );
}
