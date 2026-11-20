/**
 * Web edition: the real Python engine (FastAPI + SQLite) runs with Pyodide in a Web Worker
 * (public/engine-worker.js). The app's /api/... requests are routed to it, so no server is needed.
 * Only active in builds made with VITE_PREVIEW=1.
 */
export const PREVIEW = import.meta.env.VITE_PREVIEW === "1";

/** True when shown inside a sandboxed frame (e.g. an embedded preview), where microphone and iframes are blocked. */
export const SANDBOXED = (() => { try { return window.self !== window.top; } catch { return true; } })();

export async function bootPreview(status: (s: string) => void) {
  const base = new URL("./", location.href).href;
  const worker = new Worker(`${base}engine-worker.js`, { type: "module" });
  let nextId = 1;
  const pending = new Map<number, (r: { status: number; headers: string; body: ArrayBuffer }) => void>();

  const ready = new Promise<{ persistent: boolean }>((resolve, reject) => {
    worker.onmessage = (e) => {
      const m = e.data;
      if (m.type === "status") status(m.text);
      else if (m.type === "ready") resolve(m);
      else if (m.type === "error") reject(new Error(m.text));
      else if (m.type === "response") { pending.get(m.id)?.(m); pending.delete(m.id); }
    };
    worker.onerror = (e) => reject(new Error(e.message || "The engine worker could not start"));
  });
  worker.postMessage({ type: "boot", base });
  const info = await ready;
  // Ask Chrome not to evict this site's storage, and save immediately when the tab is hidden or closed
  try { await navigator.storage?.persist?.(); } catch { /* not supported */ }
  const flush = () => worker.postMessage({ type: "sync" });
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "hidden") flush(); });
  window.addEventListener("pagehide", flush);

  const realFetch = window.fetch.bind(window);
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const req = new Request(input, init);
    const url = new URL(req.url);
    if (url.origin !== location.origin || !url.pathname.startsWith("/api/")) return realFetch(input, init);
    const body = req.method === "GET" || req.method === "HEAD" ? null : new Uint8Array(await req.arrayBuffer());
    const id = nextId++;
    const res = await new Promise<{ status: number; headers: string; body: ArrayBuffer }>((resolve) => {
      pending.set(id, resolve);
      worker.postMessage({ type: "request", id, method: req.method, path: url.pathname, query: url.search.replace(/^\?/, ""),
        headers: JSON.stringify([...req.headers.entries()]), body }, body ? [body.buffer] : []);
    });
    const empty = res.status === 204 || res.status === 304;
    return new Response(empty ? null : res.body, { status: res.status, headers: new Headers(JSON.parse(res.headers) as [string, string][]) });
  };
  return info;
}

/** Object URLs for videos played in this visit. */
export const previewVideoUrls: Record<number, string> = {};

/** Media elements can't use the in-browser engine directly: fetch the bytes, then play them from a blob URL. */
export async function playableUrl(url: string): Promise<string> {
  if (!PREVIEW || url.startsWith("blob:") || url.startsWith("data:")) return url;
  const r = await fetch(url);
  if (!r.ok) throw new Error(`audio ${r.status}`);
  return URL.createObjectURL(await r.blob());
}
