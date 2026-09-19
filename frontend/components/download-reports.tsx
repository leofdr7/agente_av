"use client";

import { useState, useTransition } from "react";
import { toast } from "sonner";

import { generateReport } from "@/app/(app)/actions";
import { Button } from "@/components/ui/button";
import type { ReportFile } from "@/lib/api";

export function DownloadReports({
  estimationId,
}: {
  estimationId: string;
}) {
  const [reports, setReports] = useState<ReportFile[]>([]);
  const [pending, start] = useTransition();
  const [busy, setBusy] = useState<"pdf" | "docx" | null>(null);

  const download = (type: "pdf" | "docx") => {
    start(async () => {
      setBusy(type);
      try {
        let files = reports;
        if (files.length === 0) {
          const result = await generateReport(estimationId);
          if (!result.ok) {
            toast.error(result.error);
            return;
          }
          files = result.reports;
          setReports(files);
        }
        const file = files.find((item) => item.file_type === type);
        if (!file) {
          toast.error("El informe no incluyó ese formato.");
          return;
        }
        window.location.href = file.file_url;
      } finally {
        setBusy(null);
      }
    });
  };

  return (
    <div className="flex flex-col gap-2 sm:flex-row">
      <Button
        type="button"
        variant="outline"
        className="h-10 bg-sheet"
        disabled={pending}
        onClick={() => download("pdf")}
      >
        {busy === "pdf" ? "Generando PDF…" : "Descargar PDF"}
      </Button>
      <Button
        type="button"
        variant="outline"
        className="h-10 bg-sheet"
        disabled={pending}
        onClick={() => download("docx")}
      >
        {busy === "docx" ? "Generando DOCX…" : "Descargar DOCX"}
      </Button>
    </div>
  );
}
