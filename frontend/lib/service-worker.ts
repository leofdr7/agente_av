/** Keep production's PWA worker from serving stale code during development. */
export async function configureServiceWorker(production: boolean): Promise<void> {
  // #region agent log
  const debugLog = (hypothesisId: string, message: string, data: Record<string, unknown>) => {
    fetch("http://127.0.0.1:7305/ingest/112c5700-fb95-409e-b8da-cac132656b93", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Debug-Session-Id": "fabb64" },
      body: JSON.stringify({
        sessionId: "fabb64",
        runId: "pre-fix",
        hypothesisId,
        location: "lib/service-worker.ts:configureServiceWorker",
        message,
        data,
        timestamp: Date.now(),
      }),
    }).catch(() => {});
  };
  // #endregion
  if (!("serviceWorker" in navigator)) return;

  if (production) {
    await navigator.serviceWorker.register("/sw.js", { updateViaCache: "none" });
    return;
  }

  const scriptUrl = new URL("/sw.js", window.location.origin).href;
  const registrations = await navigator.serviceWorker.getRegistrations();
  // #region agent log
  debugLog("A", "dev registrations before unregister", {
    production,
    scriptUrl,
    controller: navigator.serviceWorker.controller?.scriptURL ?? null,
    registrations: registrations.map((registration) => ({
      scope: registration.scope,
      active: registration.active?.scriptURL ?? null,
      waiting: registration.waiting?.scriptURL ?? null,
      installing: registration.installing?.scriptURL ?? null,
    })),
  });
  // #endregion
  await Promise.all(
    registrations
      .filter((registration) =>
        [registration.active, registration.waiting, registration.installing].some(
          (worker) => worker?.scriptURL === scriptUrl,
        ),
      )
      .map((registration) => registration.unregister()),
  );

  // Unregistering alone does not remove Cache Storage or detach an already
  // controlled document. Clear only AgentA assets so its next request is fresh;
  // do not force a reload that could discard an employee's unsent form.
  if ("caches" in window) {
    const keys = await window.caches.keys();
    await Promise.all(
      keys
        .filter((key) => key.startsWith("agenta-static-"))
        .map((key) => window.caches.delete(key)),
    );
  }
}
