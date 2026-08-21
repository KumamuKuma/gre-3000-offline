const CACHE = "gre-3000-pwa-v20";
const CORE = [
  "/",
  "/manifest.webmanifest",
  "/icon.svg",
  "/data/words.json",
  "/data/click_dictionary.json?v=4",
  "/ECDICT-LICENSE.txt",
  "/WORDNET-LICENSE.txt",
  "/COW-LICENSE.txt",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(CORE)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key)))),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  if (
    url.pathname.startsWith("/api/") ||
    url.pathname.startsWith("/signin-with-chatgpt") ||
    url.pathname.startsWith("/signout-with-chatgpt") ||
    url.pathname.startsWith("/callback")
  ) return;
  if (url.pathname === "/data/words.json" || url.pathname === "/data/click_dictionary.json") {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          if (response.ok && url.origin === self.location.origin) {
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
        if (response.ok && url.origin === self.location.origin) {
          caches.open(CACHE).then((cache) => cache.put(event.request, response.clone()));
        }
        return response;
      });
      return cached || network.catch(() => caches.match("/"));
    }),
  );
});
