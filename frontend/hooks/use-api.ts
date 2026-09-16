"use client";

import { useAuth } from "@clerk/nextjs";
import { useCallback } from "react";

import { apiFetch, type ApiRequestInit } from "@/lib/api";

/**
 * Devuelve un `request` que adjunta el session token de Clerk a cada llamada
 * al backend desde Client Components.
 */
export function useApi() {
  const { getToken } = useAuth();

  const request = useCallback(
    <T,>(path: string, init?: ApiRequestInit) =>
      apiFetch<T>(path, () => getToken(), init),
    [getToken],
  );

  return { request };
}
