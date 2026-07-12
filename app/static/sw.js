const CACHE_NAME = "remote-c-v20-media-resume-icons";
const APP_SHELL = [
  "/",
  "/styles.css",
  "/volume.css",
  "/now-playing.css",
  "/audio-apps.css",
  "/brightness.css",
  "/output-routing.css",
  "/feedback.css",
  "/app.js",
  "/volume.js",
  "/now-playing.js",
  "/audio-apps.js",
  "/brightness.js",
  "/output-routing.js",
  "/feedback.js",
  "/manifest.webmanifest",
  "/icon.svg",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)),
    )),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  if (
    event.request.method !== "GET"
    || url.origin !== self.location.origin
    || url.pathname.startsWith("/api/")
  ) {
    return;
  }

  event.respondWith(
    fetch(event.request)
      .then(async (response) => {
        if (response.ok) {
          const copy = response.clone();
          const cache = await caches.open(CACHE_NAME);
          await cache.put(event.request, copy);
        }
        return response;
      })
      .catch(() => caches.match(event.request)),
  );
});
