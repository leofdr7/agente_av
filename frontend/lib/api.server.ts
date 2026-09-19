import { auth } from "@clerk/nextjs/server";

import { apiFetch, type ApiRequestInit } from "@/lib/api";

/**
 * Obtiene el session token de Clerk desde el contexto de servidor
 * (Server Components, Route Handlers, Server Actions).
 */
export async function getServerToken(): Promise<string | null> {
  const { getToken } = await auth();
  return getToken();
}

export function serverApiFetch<T>(path: string, init?: ApiRequestInit): Promise<T> {
  return apiFetch<T>(path, getServerToken, init);
}
