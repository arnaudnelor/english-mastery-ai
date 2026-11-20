/* English Mastery AI: web edition engine worker.
 * Runs the real Python engine (FastAPI + SQLite) with Pyodide inside a Web Worker, so the
 * interface stays responsive while the engine works (including AI requests).
 * Progress is stored in this browser (IndexedDB).
 */
const CDN = "https://cdn.jsdelivr.net/pyodide/v314.0.8/full/";
const PACKAGES = ["fastapi", "starlette", "pydantic", "pydantic-core", "typing-extensions", "typing-inspection", "annotated-types", "annotated-doc",
  "anyio", "sniffio", "sqlalchemy", "httpx", "httpcore", "h11", "idna", "certifi", "jinja2", "markupsafe"];

let py = null;
let handle = null;
let persistent = false;
let syncTimer = null;
let queue = Promise.resolve();

const status = (text) => self.postMessage({ type: "status", text });

async function boot(base) {
  status("Loading the Python runtime…");
  let indexURL = base + "pyodide/"; // local copy only when testing offline; otherwise the official CDN
  let mod;
  try { mod = await import(indexURL + "pyodide.mjs"); } catch (e) { indexURL = CDN; mod = await import(indexURL + "pyodide.mjs"); }
  py = await mod.loadPyodide({ indexURL });
  status("Installing the learning engine…");
  await py.loadPackage(PACKAGES);

  status("Restoring your progress…");
  py.FS.mkdirTree("/data");
  try {
    py.FS.mount(py.FS.filesystems.IDBFS, {}, "/data");
    await new Promise((res, rej) => py.FS.syncfs(true, (err) => (err ? rej(err) : res())));
    persistent = true;
  } catch (e) { /* no IndexedDB: progress lasts for this visit only */ }

  status("Starting the engine…");
  const engine = await (await fetch(base + "engine.json")).json();
  for (const [path, text] of Object.entries(engine.files)) {
    const full = "/engine/" + path;
    py.FS.mkdirTree(full.slice(0, full.lastIndexOf("/")));
    py.FS.writeFile(full, text);
  }
  py.runPython("import sys; sys.path[:0] = ['/engine/shims', '/engine']");
  py.runPython(engine.boot);
  handle = py.globals.get("handle");
  return { persistent };
}

function scheduleSync() {
  if (!persistent) return;
  clearTimeout(syncTimer);
  syncTimer = setTimeout(() => py.FS.syncfs(false, () => {}), 150);
}

async function request(msg) {
  const out = await handle(msg.method, msg.path, msg.query, msg.headers, msg.body);
  const [statusCode, headers, bytes] = out.toJs();
  out.destroy();
  if (msg.method !== "GET") scheduleSync();
  const buf = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
  return { status: statusCode, headers, body: buf };
}

self.onmessage = async (e) => {
  const msg = e.data;
  if (msg.type === "boot") {
    try { self.postMessage({ type: "ready", ...(await boot(msg.base)) }); }
    catch (err) { self.postMessage({ type: "error", text: String((err && err.message) || err) }); }
    return;
  }
  if (msg.type === "sync") {
    if (persistent && py) { clearTimeout(syncTimer); py.FS.syncfs(false, () => {}); }
    return;
  }
  if (msg.type === "request") {
    const run = () => request(msg).then(
      (r) => self.postMessage({ type: "response", id: msg.id, ...r }, [r.body]),
      (err) => self.postMessage({ type: "response", id: msg.id, status: 500, headers: "[]", body: new TextEncoder().encode(JSON.stringify({ detail: "Engine error: " + String(err) })).buffer }),
    );
    queue = queue.then(run, run); // one request at a time inside Python
  }
};
