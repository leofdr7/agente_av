import { UserRound } from "lucide-react";

// Account chrome only; no sign-in token, network request, or production session bypass.
export function UserButton() {
  return <button type="button" aria-label="Cuenta de prueba visual" title="Cuenta de prueba visual" className="flex size-8 items-center justify-center rounded-full border border-ink/20 bg-sheet text-ink"><UserRound size={16} aria-hidden /></button>;
}
export function ClerkProvider({ children }) { return children; }
export function useAuth() { return { getToken: async () => null }; }
