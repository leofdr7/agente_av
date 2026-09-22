/** Keep production's PWA worker from serving stale code during development. */
export async function configureServiceWorker(production: boolean): Promise<void> {
  if (!("serviceWorker" in navigator)) return;

  if (production) {
    await navigator.serviceWorker.register("/sw.js", { updateViaCache: "none" });
    return;
  }

  const scriptUrl = new URL("/sw.js", window.location.origin).href;
  const registrations = await navigator.serviceWorker.getRegistrations();
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
