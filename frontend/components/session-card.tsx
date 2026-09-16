import { UserButton } from "@clerk/nextjs";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, type Employee } from "@/lib/api";
import { serverApiFetch } from "@/lib/api.server";

type SessionState =
  | { kind: "ok"; employee: Employee }
  | { kind: "error"; message: string };

async function loadSession(): Promise<SessionState> {
  try {
    const employee = await serverApiFetch<Employee>("/api/v1/me");
    return { kind: "ok", employee };
  } catch (error) {
    if (error instanceof ApiError) {
      return {
        kind: "error",
        message: `El backend rechazó la sesión (${error.status}): ${error.message}`,
      };
    }
    return {
      kind: "error",
      message: "No se pudo contactar al backend. ¿Está uvicorn en marcha?",
    };
  }
}

export async function SessionCard() {
  const session = await loadSession();

  return (
    <Card className="bg-white/90">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Sesión</CardTitle>
        <UserButton />
      </CardHeader>
      <CardContent>
        {session.kind === "ok" ? (
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
            <dt className="text-muted-foreground">Empleado</dt>
            <dd className="font-medium">{session.employee.name}</dd>
            <dt className="text-muted-foreground">Rol</dt>
            <dd className="font-mono">{session.employee.role}</dd>
            <dt className="text-muted-foreground">Clerk ID</dt>
            <dd className="truncate font-mono">{session.employee.clerk_user_id}</dd>
          </dl>
        ) : (
          <p className="text-sm text-[#c45c26]">{session.message}</p>
        )}
      </CardContent>
    </Card>
  );
}
