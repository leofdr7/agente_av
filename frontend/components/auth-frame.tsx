import type { ReactNode } from "react";

import { InstallAppButton } from "@/components/install-app";

export function AuthFrame({ children }: { children: ReactNode }) {
  return (
    <div className="shop-grid flex min-h-dvh flex-col">
      <header className="flex items-center justify-between gap-3 border-b border-ink/10 bg-sheet/80 px-4 py-3 backdrop-blur-sm">
        <div>
          <p className="font-mono text-[11px] text-steel">TechChip · planta</p>
          <p className="text-sm font-medium text-ink">Estimaciones</p>
        </div>
        <InstallAppButton />
      </header>
      <main className="flex flex-1 items-center justify-center px-4 py-12">{children}</main>
    </div>
  );
}
