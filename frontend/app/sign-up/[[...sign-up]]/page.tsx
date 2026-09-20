import { SignUp } from "@clerk/nextjs";

import { AuthFrame } from "@/components/auth-frame";

/**
 * El registro abierto está deshabilitado en Clerk; esta ruta solo completa
 * el alta de empleados invitados desde el dashboard.
 */
export default function SignUpPage() {
  return (
    <AuthFrame>
      <SignUp />
    </AuthFrame>
  );
}
