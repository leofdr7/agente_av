/** Isolated visual verification only. Never imported by the application. */
import { createServer } from "node:http";
import { createRequire } from "node:module";
import { readFile, stat } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const frontend = path.resolve(here, "../..");
const require = createRequire(path.join(frontend, "package.json"));
const postcss = require("postcss");
const tailwind = require("@tailwindcss/postcss");

let esbuild;
const candidates = [
  process.env.AGENTA_ESBUILD_PATH,
  "esbuild",
  "/tmp/cursor-sandbox-cache/2a83d3fd33e6f86b32119859f1c50529/npm/_npx/fd45a72a545557e9/node_modules/esbuild/lib/main.js",
].filter(Boolean);
for (const candidate of candidates) {
  try {
    esbuild = require(candidate);
    break;
  } catch { /* Try the next explicitly supported dependency location. */ }
}
if (!esbuild) {
  throw new Error("Set AGENTA_ESBUILD_PATH to esbuild/lib/main.js; see verification/README.md.");
}

const aliases = {
  "next/link": path.join(here, "stubs/link.jsx"),
  "next/navigation": path.join(here, "stubs/navigation.js"),
  "@clerk/nextjs": path.join(here, "stubs/clerk.jsx"),
  "@/lib/api.server": path.join(here, "stubs/api-server.js"),
  "@/app/(app)/actions": path.join(here, "stubs/actions.js"),
};

const build = await esbuild.context({
  absWorkingDir: frontend,
  entryPoints: [path.join(here, "entry.jsx")],
  bundle: true,
  write: false,
  outfile: "/virtual/verification.js",
  format: "esm",
  platform: "browser",
  target: ["es2022"],
  jsx: "automatic",
  define: {
    "process.env.NODE_ENV": '"development"',
    "process.env.NEXT_PUBLIC_API_URL": '"http://127.0.0.1:3100/disabled-api"',
  },
  alias: aliases,
  tsconfig: path.join(frontend, "tsconfig.json"),
  logLevel: "warning",
});

// Parse the literal fixture text, preserving Python's escaped line continuations.
const fixtureSource = await readFile(path.resolve(frontend, "../backend/tests/fixtures/panaderia.py"), "utf8");
const fixtureMatch = fixtureSource.match(/PROBLEM_TEXT\s*=\s*"""([\s\S]*?)"""/);
if (!fixtureMatch) throw new Error("Could not find the bakery fixture PROBLEM_TEXT.");
const problemText = fixtureMatch[1].replaceAll("\\\n", "");
const run = JSON.parse(await readFile(path.join(here, "panaderia-run.json"), "utf8"));

// Only project metadata is illustrative. The saved result_json is unmodified.
const createdAt = "2026-09-21T16:30:00-06:00";
const project = {
  id: "visual-panaderia",
  name: "Panadería / producción diaria",
  budget: 1250,
  status: "active",
  created_by: "visual-fixture",
  created_at: createdAt,
  updated_at: createdAt,
};
const projects = [
  project,
  { ...project, id: "visual-turno", name: "Planificación del turno de mañana", budget: 3200, status: "draft" },
  { ...project, id: "visual-recursos", name: "Asignación semanal de recursos", budget: 8750, status: "completed" },
  { ...project, id: "visual-expansion", name: "Ampliación de capacidad", budget: null, status: "on_hold" },
];
const estimation = {
  id: run.estimation_id,
  problem_text: problemText,
  result_json: run.result_json,
  project_id: project.id,
  project,
  requested_by: "visual-fixture",
  created_at: createdAt,
  reports: [],
};
const fixtures = {
  projects,
  estimation,
  estimations: [{
    id: estimation.id,
    problem_text: estimation.problem_text,
    project_id: project.id,
    project_name: project.name,
    requested_by: estimation.requested_by,
    created_at: createdAt,
  }],
};

const html = `<!doctype html>
<html lang="es" class="h-full antialiased">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover" />
  <meta name="description" content="Isolated AgentA visual verification: actual source components, saved bakery calculation, illustrative project metadata. Authentication and network actions are mocked only here." />
  <title>AgentA / verificación visual aislada</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Fragment+Mono:ital@0;1&family=Instrument+Sans:wght@400;500;600;700&display=swap" rel="stylesheet" />
  <link href="/verification.css" rel="stylesheet" />
  <style>:root{--font-instrument-sans:"Instrument Sans",sans-serif;--font-fragment-mono:"Fragment Mono",monospace}</style>
</head>
<body class="flex min-h-full flex-col font-sans">
  <div id="root"></div>
  <script type="module" src="/verification.js"></script>
</body>
</html>`;

const port = Number(process.env.AGENTA_VISUAL_PORT ?? 3100);
const server = createServer(async (request, response) => {
  try {
    const url = new URL(request.url ?? "/", `http://127.0.0.1:${port}`);
    response.setHeader("Cache-Control", "no-store");
    response.setHeader("X-Content-Type-Options", "nosniff");
    if (request.method !== "GET") {
      response.writeHead(405).end("This visual fixture server is read-only.");
    } else if (url.pathname === "/verification.js") {
      const result = await build.rebuild();
      response.writeHead(200, { "Content-Type": "text/javascript; charset=utf-8" }).end(result.outputFiles.find((file) => file.path.endsWith(".js")).text);
    } else if (url.pathname === "/verification.css") {
      const cssFile = path.join(frontend, "app/globals.css");
      const css = await readFile(cssFile, "utf8");
      const result = await postcss([tailwind({ base: frontend })]).process(css, { from: cssFile });
      const bundle = await build.rebuild();
      const componentCss = bundle.outputFiles.find((file) => file.path.endsWith(".css"))?.text ?? "";
      response.writeHead(200, { "Content-Type": "text/css; charset=utf-8" }).end(`${result.css}\n${componentCss}`);
    } else if (url.pathname === "/fixture.json") {
      response.writeHead(200, { "Content-Type": "application/json; charset=utf-8" }).end(JSON.stringify(fixtures));
    } else if (url.pathname === "/favicon.ico") {
      response.writeHead(204).end();
    } else if (url.pathname === "/logo.png" || url.pathname === "/icon.png" || /^\/icons\/[a-z0-9-]+\.png$/.test(url.pathname)) {
      const asset = url.pathname === "/icon.png"
        ? path.join(frontend, "app/icon.png")
        : path.join(frontend, "public", url.pathname);
      await stat(asset);
      response.writeHead(200, { "Content-Type": "image/png" }).end(await readFile(asset));
    } else {
      response.writeHead(200, { "Content-Type": "text/html; charset=utf-8" }).end(html);
    }
  } catch (error) {
    console.error(error);
    response.writeHead(500, { "Content-Type": "text/plain; charset=utf-8" }).end(String(error));
  }
});

server.listen(port, "127.0.0.1", () => {
  console.log(`Visual verification: http://127.0.0.1:${port}`);
  console.log("Screens: ?screen=projects, ?screen=new, ?screen=result, ?screen=history");
  console.log("Options: &theme=dark, &panels=open, &state=empty, &state=error");
  console.log("Actual source components; saved calculation fixture; isolated auth/action stubs.");
});

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, async () => {
    server.close();
    await build.dispose();
    process.exit(0);
  });
}
