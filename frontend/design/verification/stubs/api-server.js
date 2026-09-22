// Deliberately fixture-only. This alias is installed by serve.mjs, never by Next.
let fixturePromise;
export function getFixture() {
  fixturePromise ??= fetch("/fixture.json").then((response) => response.json());
  return fixturePromise;
}

export async function serverApiFetch(path) {
  const query = new URLSearchParams(window.location.search);
  if (query.get("state") === "error") throw new Error("Ejemplo de servicio temporalmente no disponible.");
  const fixture = await getFixture();
  const empty = query.get("state") === "empty";
  if (path === "/api/v1/projects") return empty ? [] : fixture.projects;
  if (path === "/api/v1/estimations" || /^\/api\/v1\/projects\/[^/]+\/estimations$/.test(path)) {
    return empty ? [] : fixture.estimations;
  }
  if (/^\/api\/v1\/estimations\/[^/]+$/.test(path)) return fixture.estimation;
  if (/^\/api\/v1\/projects\/[^/]+$/.test(path)) return fixture.estimation.project;
  throw new Error(`No visual fixture for ${path}`);
}
