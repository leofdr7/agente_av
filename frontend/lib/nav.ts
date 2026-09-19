import type { LucideIcon } from "lucide-react";
import { ClipboardList, FolderKanban, Plus } from "lucide-react";

export type NavHref = "/" | "/nueva" | "/historial";

export interface NavItem {
  href: NavHref;
  label: string;
  icon: LucideIcon;
}

export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Proyectos", icon: FolderKanban },
  { href: "/nueva", label: "Nueva", icon: Plus },
  { href: "/historial", label: "Historial", icon: ClipboardList },
];

export function isNavActive(pathname: string, href: NavHref): boolean {
  if (href === "/") {
    return pathname === "/" || pathname.startsWith("/proyectos/");
  }
  if (href === "/historial") {
    return pathname === "/historial" || pathname.startsWith("/estimaciones/");
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}
