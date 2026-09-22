import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";

const workerSource = readFileSync(new URL("../public/sw.js", import.meta.url), "utf8");
const lifecycleSource = ts.transpileModule(
  readFileSync(new URL("../lib/service-worker.ts", import.meta.url), "utf8"),
  { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } },
).outputText;
const origin = "http://localhost:3000";

function storage(initial = {}) {
  const entries = new Map(Object.entries(initial));
  return {
    entries,
    keys: async () => [...entries.keys()],
    delete: async (key) => entries.delete(key),
    open: async (key) => {
      if (!entries.has(key)) entries.set(key, new Map());
      const cache = entries.get(key);
      return {
        match: async (request) => cache.get(request.url),
        put: async (request, response) => cache.set(request.url, response),
        addAll: async (urls) => urls.forEach((url) => cache.set(origin + url, { icon: true })),
      };
    },
  };
}

function worker(caches, fetch = async () => { throw new Error("Unexpected network request"); }) {
  const handlers = {};
  let claimed = false;
  vm.runInNewContext(workerSource, {
    URL,
    caches,
    fetch,
    self: {
      location: new URL(origin),
      addEventListener: (name, handler) => { handlers[name] = handler; },
      clients: { claim: async () => { claimed = true; } },
      skipWaiting: async () => {},
    },
  });
  return {
    claimed: () => claimed,
    lifecycle: (name) => new Promise((resolve, reject) => {
      handlers[name]({ waitUntil: (promise) => promise.then(resolve, reject) });
    }),
    request: (url, method = "GET") => {
      let response;
      handlers.fetch({
        request: { url: new URL(url, origin).href, method },
        respondWith: (promise) => { response = promise; },
      });
      return response;
    },
  };
}

function configure(navigator, caches) {
  const exports = {};
  vm.runInNewContext(lifecycleSource, {
    exports,
    URL,
    navigator,
    window: { location: { origin }, ...(caches ? { caches } : {}) },
  });
  return exports.configureServiceWorker;
}

test("stale Next chunks never supply the client, even when present in Cache Storage", async () => {
  const chunk = `${origin}/_next/static/chunks/app-shell.js`;
  const oldClient = { html: '<div class="shop-grid min-h-dvh">' };
  const caches = storage({
    "agenta-static-v1": new Map([[chunk, oldClient]]),
    "agenta-static-v2": new Map([[chunk, oldClient]]),
  });
  const sw = worker(caches);
  for (const url of [chunk, "/_next/static/chunks/app.css", "/_next/static/media/font.woff2", "/_next/webpack-hmr"]) {
    assert.equal(sw.request(url), undefined, `Next must handle ${url}`);
  }
});

test("activation removes old AgentA code caches, preserves other applications and claims clients", async () => {
  const caches = storage({
    "agenta-static-v1": new Map(),
    "agenta-static-v2": new Map(),
    "agenta-static-v3": new Map(),
    "other-app": new Map(),
  });
  const sw = worker(caches);
  await sw.lifecycle("activate");
  assert.deepEqual(await caches.keys(), ["agenta-static-v3", "other-app"]);
  assert.equal(sw.claimed(), true);
});

test("PWA icons still install and work offline from cache", async () => {
  const sw = worker(storage());
  await sw.lifecycle("install");
  assert.equal((await sw.request("/icons/icon-192.png")).icon, true);
});

test("HTML, APIs, authenticated files and other origins bypass the worker", () => {
  const sw = worker(storage());
  for (const url of ["/", "/nueva", "/api/v1/projects", "/reports/private.png", "http://localhost:8000/icons/icon-192.png", "https://localhost:3000/icons/icon-192.png"]) {
    assert.equal(sw.request(url), undefined);
  }
  assert.equal(sw.request("/icons/icon-192.png", "POST"), undefined);
});

test("development unregisters only AgentA workers and removes only its caches", async () => {
  const removed = [];
  const caches = storage({ "agenta-static-v1": new Map(), "other-app": new Map() });
  const registration = (field, scriptURL) => ({
    [field]: { scriptURL },
    unregister: async () => { removed.push(scriptURL); },
  });
  const serviceWorker = {
    getRegistrations: async () => [
      registration("active", `${origin}/sw.js`),
      registration("waiting", `${origin}/sw.js`),
      registration("installing", `${origin}/sw.js`),
      registration("active", `${origin}/other/sw.js`),
    ],
  };
  await configure({ serviceWorker }, caches)(false);
  assert.deepEqual(removed, Array(3).fill(`${origin}/sw.js`));
  assert.deepEqual(await caches.keys(), ["other-app"]);
});

test("production continues registering the PWA without cached worker updates", async () => {
  const calls = [];
  const caches = storage({ "agenta-static-v1": new Map() });
  const serviceWorker = { register: async (...args) => { calls.push(args); } };
  await configure({ serviceWorker }, caches)(true);
  assert.equal(calls[0][0], "/sw.js");
  assert.equal(calls[0][1].updateViaCache, "none");
  assert.deepEqual(await caches.keys(), ["agenta-static-v1"]);
});

test("browsers without service workers or Cache Storage remain supported", async () => {
  await configure({}, undefined)(false);
  await configure({ serviceWorker: { getRegistrations: async () => [] } }, undefined)(false);
});
