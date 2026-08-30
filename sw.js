/* 最小限の Service Worker: 全アセットを事前キャッシュし、キャッシュ優先で返す。
   dishes.yaml や index.html を更新して配信し直すときは CACHE_VERSION を上げること。 */
const CACHE_VERSION = "konya-v4";
const ASSETS = ["./", "./index.html", "./dishes.json", "./manifest.json"];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE_VERSION).then((c) => c.addAll(ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;
  e.respondWith(
    caches.match(e.request, { ignoreSearch: true }).then((hit) => hit || fetch(e.request))
  );
});
