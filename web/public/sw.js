const scope = new URL(self.registration.scope);
const scopePath = scope.pathname.slice(0, -1);
const cacheVersion = "gre-3000-pwa-v30";
const CACHE = scopePath ? `${cacheVersion}:${scopePath}` : cacheVersion;
const CORE = [
  "/",
  "/manifest.webmanifest",
  "/icon.svg",
  "/icon-192.png",
  "/icon-512.png",
  "/apple-touch-icon.png",
  "/data/words.json",
  "/data/long_sentences.json?v=2",
  "/data/click_dictionary.json?v=6",
  "/ECDICT-LICENSE.txt",
  "/WORDNET-LICENSE.txt",
  "/COW-LICENSE.txt",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(CORE.map((path) => `${scopePath}${path}`))));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((key) => {
      const match = /^gre-3000-pwa-v\d+(?::(.*))?$/.exec(key);
      return match && (match[1] ?? "") === scopePath && key !== CACHE;
    }).map((key) => caches.delete(key)))),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  if (url.origin !== scope.origin || !url.pathname.startsWith(scope.pathname)) return;
  const pathname = url.pathname.slice(scopePath.length);
  if (
    pathname.startsWith("/api/") ||
    pathname.startsWith("/signin-with-chatgpt") ||
    pathname.startsWith("/signout-with-chatgpt") ||
    pathname.startsWith("/callback")
  ) return;
  if (
    pathname === "/data/words.json"
    || pathname === "/data/long_sentences.json"
    || pathname === "/data/click_dictionary.json"
  ) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          if (response.ok) {
            caches.open(CACHE).then((cache) => cache.put(event.request, response.clone()));
          }
          return response;
        })
        .catch((error) => caches.match(event.request).then((cached) => cached || Promise.reject(error))),
    );
    return;
  }
  event.respondWith(
    caches.match(event.request).then((cached) => {
      const network = fetch(event.request).then((response) => {
          if (response.ok) {
          caches.open(CACHE).then((cache) => cache.put(event.request, response.clone()));
        }
        return response;
      });
      return cached || network.catch(() => caches.match(scope.href));
    }),
  );
});
