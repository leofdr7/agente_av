"use client";

import { useEffect } from "react";

import { configureServiceWorker } from "@/lib/service-worker";

export function RegisterServiceWorker() {
  useEffect(() => {
    void configureServiceWorker(process.env.NODE_ENV === "production").catch(
      (error: unknown) => console.warn("No se pudo configurar la caché de AgentA.", error),
    );
  }, []);

  return null;
}
