const CACHE_PREFIX = "agenta-static-";
const CACHE_NAME = `${CACHE_PREFIX}v3`;

const PRECACHE_URLS = [
  "/icons/icon-48.png",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/icons/icon-192-maskable.png",
  "/icons/icon-512-maskable.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key.startsWith(CACHE_PREFIX) && key !== CACHE_NAME)
            .map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

function isStaticAsset(requestUrl) {
  const { pathname, origin } = new URL(requestUrl);
  if (origin !== self.location.origin) return false;
  // Next controls its own versioned assets. In development its chunk URLs can
  // be reused: cache-first here mixes an old client with newly rendered HTML.
  if (pathname.startsWith("/_next/")) return false;
  if (pathname.startsWith("/icons/")) return true;
  return ["/favicon.ico", "/icon.png", "/apple-icon.png"].includes(pathname);
}

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  if (!isStaticAsset(event.request.url)) return;

  event.respondWith(
    caches.open(CACHE_NAME).then(async (cache) => {
      const cached = await cache.match(event.request);
      if (cached) return cached;
      const response = await fetch(event.request);
      if (response.ok) {
        cache.put(event.request, response.clone());
      }
      return response;
    }),
  );
});
