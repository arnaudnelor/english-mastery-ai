// In Electron production the backend serves the UI, so relative URLs work.
// In `vite` dev mode, the dev server proxies /api to the backend.
const BASE = "";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(BASE + path, init);
  } catch {
    throw new ApiError(0, "Cannot reach the local learning engine. Restart the app.");
  }
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const b = await res.json();
      msg = typeof b.detail === "string" ? b.detail : JSON.stringify(b.detail);
    } catch { /* ignore */ }
    throw new ApiError(res.status, msg);
  }
  return res.json() as Promise<T>;
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
};

// ---------- shared types ----------
export interface Profile {
  id: number; name: string; target_level: string; estimated_level: string; daily_minutes: number;
  accent_preference: "en-CA" | "en-US" | "en-GB"; correction_mode: string; french_explanations: boolean;
  reminder_time: string | null; placement_done?: boolean;
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
