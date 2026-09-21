"use client";

import type { ReactNode } from "react";
import { UserButton } from "@clerk/nextjs";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { InstallAppButton } from "@/components/install-app";
import { isNavActive, NAV_ITEMS } from "@/lib/nav";
import { cn } from "cn";

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="shop-grid min-h-dvh">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-56 flex-col border-r border-ink/10 bg-sidebar/90 px-3 py-5 backdrop-blur-sm md:flex">
        <p className="px-2 font-mono text-[11px] tracking-wide text-steel">
          AgentA · planta
        </p>
        <p className="mt-1 px-2 text-sm font-medium text-ink">Estimaciones</p>
        <nav className="mt-8 flex flex-1 flex-col gap-1" aria-label="Principal">
          {NAV_ITEMS.map((item) => {
            const active = isNavActive(pathname, item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-2 rounded-md px-2 py-2 text-sm transition-colors",
                  active
                    ? "bg-sheet text-ink shadow-[inset_3px_0_0_var(--copper)]"
                    : "text-steel hover:bg-sheet/70 hover:text-ink",
                )}
              >
                <Icon className="size-4 shrink-0" aria-hidden />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="flex items-center gap-2 px-1 pt-4">
          <InstallAppButton />
          <UserButton />
        </div>
      </aside>

      <div className="flex min-h-dvh flex-col md:pl-56">
        <header className="flex items-center justify-between gap-3 border-b border-ink/10 bg-sheet/80 px-4 py-3 backdrop-blur-sm md:hidden">
          <div>
            <p className="font-mono text-[11px] text-steel">AgentA · planta</p>
            <p className="text-sm font-medium text-ink">Estimaciones</p>
          </div>
          <div className="flex items-center gap-2">
            <InstallAppButton />
            <UserButton />
          </div>
        </header>

        <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-6 pb-[calc(5.25rem+env(safe-area-inset-bottom))] md:px-8 md:py-8 md:pb-10">
          {children}
        </main>
      </div>

      <nav
        aria-label="Principal"
        className="fixed inset-x-0 bottom-0 z-30 border-t border-ink/10 bg-sheet/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-sm md:hidden"
      >
        <ul className="grid grid-cols-3">
          {NAV_ITEMS.map((item) => {
            const active = isNavActive(pathname, item.href);
            const Icon = item.icon;
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={cn(
                    "flex flex-col items-center gap-1 px-2 py-2.5 text-[11px]",
                    active ? "text-copper" : "text-steel",
                  )}
                >
                  <Icon className="size-5" aria-hidden />
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </div>
  );
}
