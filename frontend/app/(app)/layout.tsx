import type { ReactNode } from "react";

import { AppShell } from "@/components/app-shell";

export const maxDuration = 120;

export default function AppLayout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
