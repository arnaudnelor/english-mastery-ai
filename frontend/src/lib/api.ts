// Desktop app: the backend serves the UI, so relative URLs work (vite dev proxies /api).
// Hosted academy (VITE_HOSTED=1): the UI is on GitHub Pages and the API on its own HTTPS server.
export const HOSTED = import.meta.env.VITE_HOSTED === "1";
export const API_BASE: string = HOSTED ? (import.meta.env.VITE_API_BASE ?? "") : "";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

// ---------- session token (hosted academy) ----------
const TOKEN_KEY = "ema_token";
let token: string | null = null;
try { token = localStorage.getItem(TOKEN_KEY); } catch { /* storage blocked */ }
export const auth = {
  get: () => token,
  set(t: string | null) {
    token = t;
    try { if (t) localStorage.setItem(TOKEN_KEY, t); else localStorage.removeItem(TOKEN_KEY); } catch { /* ignore */ }
  },
};

// ---------- save status (shown as "Saving… / Saved successfully / Unable to save — retrying") ----------
export type SaveState = "idle" | "saving" | "saved" | "retrying" | "waking";
let saveState: SaveState = "idle";
const listeners = new Set<(s: SaveState) => void>();
let inflight = 0;
function setSave(s: SaveState) { saveState = s; listeners.forEach((l) => l(s)); }
export const saveStatus = {
  get: () => saveState,
  subscribe(l: (s: SaveState) => void) { listeners.add(l); return () => { listeners.delete(l); }; },
};

/** Writes that are safe to repeat: they're queued and retried until the server confirms them. */
const SAFE_RETRY = [/\/answer$/, /^\/api\/vocabulary\/review\//, /^\/api\/academy\/(visit|heartbeat)$/, /^\/api\/vocabulary\/deck/,
  /^\/api\/profile$/, /^\/api\/auth\/me$/, /^\/api\/listening\/[^/]+\/(dictation|gaps)/, /^\/api\/pronunciation\/pairs/];
const OUTBOX_KEY = "ema_outbox";
interface Pending { path: string; method: string; body: string; at: number }
function readOutbox(): Pending[] { try { return JSON.parse(localStorage.getItem(OUTBOX_KEY) || "[]"); } catch { return []; } }
function writeOutbox(items: Pending[]) { try { localStorage.setItem(OUTBOX_KEY, JSON.stringify(items.slice(-200))); } catch { /* ignore */ } }

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function rawFetch(path: string, init: RequestInit): Promise<Response> {
  const headers = new Headers(init.headers);
  if (HOSTED && token) headers.set("Authorization", `Bearer ${token}`);
  return fetch(API_BASE + path, { ...init, headers });
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  // Background writes (study-time heartbeats, sign-in) don't flash the save indicator.
  const background = /^\/api\/(academy\/(visit|heartbeat)|auth\/(notifications\/read|logout|login|register|config|setup-admin))$/.test(path.split("?")[0]);
  const write = (init.method ?? "GET") !== "GET" && !background;
  const safe = (init.method ?? "GET") !== "GET" && typeof init.body === "string" && SAFE_RETRY.some((r) => r.test(path.split("?")[0]));
  if (write) { inflight++; setSave("saving"); }
  const slow = setTimeout(() => setSave("waking"), 5000); // free hosting sleeps when idle: first call can take ~1 minute
  try {
    let res: Response | null = null;
    const isWrite = (init.method ?? "GET") !== "GET";
    for (let attempt = 0; attempt < (safe || !isWrite ? 4 : 1); attempt++) {
      try {
        res = await rawFetch(path, init);
        if (![502, 503, 504].includes(res.status)) break; // server waking up / restarting
      } catch { res = null; }
      if (attempt < 3) { if (write) setSave("retrying"); await sleep([1500, 4000, 9000][attempt]); }
    }
    if (!res || [502, 503, 504].includes(res.status)) {
      if (safe) {
        writeOutbox([...readOutbox(), { path, method: init.method!, body: init.body as string, at: Date.now() }]);
        setSave("retrying");
        scheduleFlush();
        throw new ApiError(0, "Unable to save right now — your answer is kept on this device and will be sent automatically when the connection returns.");
      }
      throw new ApiError(0, HOSTED ? "Can't reach the academy server. Check your internet connection and try again." : "Cannot reach the local learning engine. Restart the app.");
    }
    if (res.status === 401 && HOSTED && !path.startsWith("/api/auth/")) {
      auth.set(null);
      window.dispatchEvent(new Event("ema-signed-out"));
    }
    if (!res.ok) {
      let msg = res.statusText;
      try {
        const b = await res.json();
        msg = typeof b.detail === "string" ? b.detail : Array.isArray(b.detail) ? b.detail.map((d: { msg: string; loc?: string[] }) => `${d.loc?.slice(-1)[0] ?? ""}: ${d.msg}`).join("; ") : JSON.stringify(b.detail);
      } catch { /* ignore */ }
      throw new ApiError(res.status, msg);
    }
    const ct = res.headers.get("content-type") ?? "";
    return (ct.includes("application/json") ? res.json() : res.blob()) as Promise<T>;
  } finally {
    clearTimeout(slow);
    if (write) { inflight = Math.max(0, inflight - 1); if (!inflight && saveState !== "retrying") { setSave("saved"); setTimeout(() => saveState === "saved" && setSave("idle"), 2500); } }
    else if (saveState === "waking") setSave("idle");
  }
}

let flushTimer: number | undefined;
function scheduleFlush() { if (!flushTimer) flushTimer = window.setTimeout(flushOutbox, 15000); }
export async function flushOutbox() {
  flushTimer = undefined;
  const items = readOutbox();
  if (!items.length) return;
  const left: Pending[] = [];
  for (const it of items) {
    try {
      const r = await rawFetch(it.path, { method: it.method, headers: { "Content-Type": "application/json" }, body: it.body });
      if ([502, 503, 504].includes(r.status)) left.push(it);
    } catch { left.push(it); }
  }
  writeOutbox(left);
  if (left.length) { setSave("retrying"); scheduleFlush(); } else { setSave("saved"); setTimeout(() => saveState === "saved" && setSave("idle"), 2500); }
}
if (typeof window !== "undefined") {
  window.addEventListener("online", () => { flushOutbox(); });
  setTimeout(flushOutbox, 3000);
}

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: body === undefined ? undefined : JSON.stringify(body),
});

export const api = {
  get: <T,>(p: string) => request<T>(p),
  post: <T,>(p: string, body?: unknown) => request<T>(p, json("POST", body ?? {})),
  put: <T,>(p: string, body: unknown) => request<T>(p, json("PUT", body)),
  del: <T,>(p: string) => request<T>(p, { method: "DELETE" }),
  upload: <T,>(p: string, form: FormData) => request<T>(p, { method: "POST", body: form }),
  /** Fetch a file (PDF, spreadsheet, audio) with the session and save it / return a blob URL. */
  async blob(p: string): Promise<Blob> {
    const r = await rawFetch(p, {});
    if (!r.ok) { let m = r.statusText; try { m = (await r.json()).detail; } catch { /* binary */ } throw new ApiError(r.status, m); }
    return r.blob();
  },
  async download(p: string, filename: string) {
    const b = await api.blob(p);
    const url = URL.createObjectURL(b);
    const a = document.createElement("a");
    a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  },
};

// ---------- shared types ----------
export interface Profile {
  id: number; name: string; target_level: string; estimated_level: string; daily_minutes: number;
  accent_preference: "en-CA" | "en-US" | "en-GB"; correction_mode: string; french_explanations: boolean;
  reminder_time: string | null; placement_done?: boolean; level_confirmed?: boolean;
}
export interface Issue { category: string; original: string; corrected: string; explanation: string; pattern?: string; explanation_fr?: string | null }
export interface Feedback {
  corrected_sentence: string; is_correct: boolean; issues: Issue[]; advanced_alternative?: string | null;
  repeat_prompt?: string | null; fluency_note?: string | null; score: number;
}
export interface SpeechMetrics { word_count: number; duration_sec: number; words_per_minute: number | null; long_pauses: number; longest_pause_sec: number; filler_words: number }
export interface TurnResult { transcript: string; reply: string; feedback: Feedback | null; feedback_deferred: boolean; speech_metrics: SpeechMetrics | null }
export interface Word {
  id: string; word: string; ipa: string; pos: string; level: string; domain: string; definition: string;
  examples: string[]; synonyms: string[]; antonyms: string[]; collocations: string[]; french: string; kind: string;
  status?: string; in_deck?: boolean;
}
export interface Feature { id: string; name: string; status: "available" | "planned"; needs?: string[]; phase?: number }
