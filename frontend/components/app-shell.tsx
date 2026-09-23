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
    <div className="min-h-dvh bg-paper">
      <a href="#main-content" className="sr-only z-50 bg-sheet p-3 text-ink focus:fixed focus:left-4 focus:top-4 focus:not-sr-only">
        Ir al contenido
      </a>
      <aside className="app-sidebar fixed inset-y-0 left-0 z-30 hidden flex-col border-r border-border md:flex">
        <Brand />
        <nav className="mt-12 flex flex-1 flex-col gap-2" aria-label="Principal">
          {NAV_ITEMS.map((item) => {
            const active = isNavActive(pathname, item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className="app-nav-link"
              >
                <Icon className="size-[18px] shrink-0" aria-hidden />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="flex items-center gap-3 border-t border-border px-1 pt-5">
          <InstallAppButton />
          <UserButton />
        </div>
      </aside>

      <div className="flex min-h-dvh flex-col md:pl-56">
        <header className="flex items-center justify-between gap-3 border-b border-border bg-sheet px-5 py-4 md:hidden">
          <Brand />
          <div className="flex items-center gap-2">
            <InstallAppButton />
            <UserButton />
          </div>
        </header>

        <main id="main-content" tabIndex={-1} className="app-main mx-auto flex-1">
          {children}
        </main>
      </div>

      <nav
        aria-label="Principal"
        className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-sheet pb-[env(safe-area-inset-bottom)] md:hidden"
      >
        <ul className="grid grid-cols-3">
          {NAV_ITEMS.map((item) => {
            const active = isNavActive(pathname, item.href);
            const Icon = item.icon;
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex min-h-16 flex-col items-center justify-center gap-1 border-t-[3px] px-2 py-2 text-xs font-medium",
                    active ? "border-primary bg-accent text-primary" : "border-transparent text-steel",
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

function Brand() {
  return (
    <div className="brand-lockup">
      <img src="/logo.png" alt="" width={40} height={40} className="brand-mark" />
      <div>
        <p className="brand-name">AgentA</p>
        <p className="brand-description">Estimaciones</p>
      </div>
    </div>
  );
}
