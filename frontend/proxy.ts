import { clerkMiddleware } from "@clerk/nextjs/server";
import type { NextRequest } from "next/server";

/**
 * Rutas accesibles sin sesión. Todo lo demás exige un usuario autenticado.
 * `/sign-up` queda pública solo para completar invitaciones: el registro
 * abierto se deshabilita desde el dashboard de Clerk (ver README).
 */
const PUBLIC_PATH_PREFIXES = ["/sign-in", "/sign-up"];

function isPublicRoute(request: NextRequest): boolean {
  const { pathname } = request.nextUrl;
  return PUBLIC_PATH_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}

export default clerkMiddleware(async (auth, request) => {
  if (!isPublicRoute(request)) {
    await auth.protect();
  }
});

export const config = {
  matcher: [
    // Omite internos de Next.js y archivos estáticos, salvo que aparezcan en search params.
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    // Siempre se ejecuta para rutas API.
    "/(api|trpc)(.*)",
  ],
};
