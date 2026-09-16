import { SignUp } from "@clerk/nextjs";

/**
 * El registro abierto está deshabilitado en Clerk; esta ruta solo completa
 * el alta de empleados invitados desde el dashboard.
 */
export default function SignUpPage() {
  return (
    <main className="flex flex-1 items-center justify-center bg-[#dfe6ee] px-4 py-12">
      <SignUp />
    </main>
  );
}
