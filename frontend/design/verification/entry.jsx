import { createRoot } from "react-dom/client";
import DashboardPage from "@/app/(app)/page";
import NuevaPage from "@/app/(app)/nueva/page";
import HistorialPage from "@/app/(app)/historial/page";
import EstimacionPage from "@/app/(app)/estimaciones/[id]/page";
import ProyectoPage from "@/app/(app)/proyectos/[id]/page";
import { AppShell } from "@/components/app-shell";
import { Toaster } from "@/components/ui/sonner";
import { getFixture } from "./stubs/api-server.js";
import { selectedScreen } from "./stubs/navigation.js";

const query = new URLSearchParams(window.location.search);
document.documentElement.classList.toggle("dark", query.get("theme") === "dark");
const fixture = await getFixture();
const screen = selectedScreen();
const pages = {
  projects: () => DashboardPage(),
  new: () => NuevaPage(),
  history: () => HistorialPage(),
  result: () => EstimacionPage({ params: Promise.resolve({ id: fixture.estimation.id }) }),
  project: () => ProyectoPage({ params: Promise.resolve({ id: fixture.estimation.project_id }) }),
};

try {
  // Async server exports only select fixtures; their real JSX and client components mount intact.
  const page = await (pages[screen] ?? pages.projects)();
  createRoot(document.getElementById("root")).render(<><AppShell>{page}</AppShell><Toaster /></>);
  const observe = new MutationObserver(() => {
    if (query.get("panels") === "open") {
      document.querySelectorAll("details").forEach((panel) => { panel.open = true; });
    }
    if (document.querySelector("main")) {
      document.documentElement.dataset.visualReady = "true";
      observe.disconnect();
    }
  });
  observe.observe(document.getElementById("root"), { subtree: true, childList: true });
} catch (error) {
  document.getElementById("root").textContent = `Visual harness failed: ${String(error)}`;
  console.error(error);
}
