export function selectedScreen() {
  const query = new URLSearchParams(window.location.search).get("screen");
  if (query) return query;
  if (window.location.pathname.startsWith("/estimaciones/")) return "result";
  if (window.location.pathname.startsWith("/proyectos/")) return "project";
  if (window.location.pathname === "/historial") return "history";
  if (window.location.pathname === "/nueva") return "new";
  return "projects";
}
export function usePathname() {
  const paths = { projects: "/", new: "/nueva", history: "/historial", result: "/estimaciones/fixture", project: "/proyectos/fixture" };
  return paths[selectedScreen()] ?? "/";
}
export function notFound() { throw new Error("Fixture not found"); }
export function redirect() { throw new Error("Redirect is disabled in the visual harness"); }
