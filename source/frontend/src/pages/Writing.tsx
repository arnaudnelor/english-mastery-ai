import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../lib/api";
import { CategoryPill, ErrorBox } from "../components/ui";

interface Result {
  improved_text: string; original_text: string;
  issues: { category: string; original: string; corrected: string; explanation: string }[];
  repeated_words: string[]; scores: Record<string, number>; overall: number;
  practice_band_estimate: number | null; advanced_expressions: { instead_of: string; try: string }[];
  next_exercise: string; disclaimer?: string;
}

export default function Writing() {
  const [genres, setGenres] = useState<Record<string, string>>({});
  const [params] = useSearchParams();
  const [genre, setGenre] = useState(params.get("genre") ?? "email");
  const [task, setTask] = useState(params.get("task") ?? "");
  const lessonId = params.get("lesson");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<Result | null>(null);
  const [err, setErr] = useState<{ msg: string; key: boolean } | null>(null);
  useEffect(() => { api.get<Record<string, string>>("/api/writing/genres").then(setGenres); }, []);

  async function submit() {
    setBusy(true); setErr(null);
    try { setRes(await api.post<Result>("/api/writing/evaluate", { genre, text, task: task || null, lesson_id: lessonId })); }
    catch (e) { const a = e as ApiError; setErr({ msg: a.message, key: a.status === 412 }); }
    finally { setBusy(false); }
  }
  const words = text.trim() ? text.trim().split(/\s+/).length : 0;

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div><h1 className="h1">Writing Masterclass</h1><p className="muted mt-1">Write, then get line-by-line corrections, scores and a before/after comparison.</p></div>
      {lessonId && task && <div className="card !border-brand-400 !py-3 text-sm"><span className="label">Academy writing assignment</span>{task}</div>}
      <div className="grid grid-cols-2 gap-6">
        <div className="card space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div><label className="label">Type</label><select className="input" value={genre} onChange={(e) => setGenre(e.target.value)}>{Object.entries(genres).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></div>
            <div><label className="label">Task (optional)</label><input className="input" value={task} onChange={(e) => setTask(e.target.value)} placeholder="e.g. Ask your manager for a deadline extension" /></div>
          </div>
          <textarea className="input min-h-[360px] font-serif leading-relaxed" value={text} onChange={(e) => setText(e.target.value)} placeholder="Start writing…" />
          <div className="flex items-center justify-between"><span className="text-xs text-ink-400">{words} words</span><button className="btn-primary" disabled={busy || words < 5} onClick={submit}>{busy ? "Evaluating…" : "Evaluate my writing"}</button></div>
          {err && <ErrorBox msg={err.msg} action={err.key ? <Link to="/settings" className="underline">Open Settings</Link> : undefined} />}
        </div>
        <div className="card space-y-4">
          {!res ? <p className="muted">Your corrected version and feedback will appear here.</p> : (
            <>
              <div className="flex items-center justify-between"><h2 className="font-semibold">Improved version</h2>
                <div className="text-right"><span className="font-serif text-2xl">{Math.round(res.overall * 100)}%</span>{res.practice_band_estimate != null && <div className="text-xs text-ink-400">Practice band ≈ {res.practice_band_estimate}</div>}</div></div>
              {res.disclaimer && <p className="text-xs text-gold-500">{res.disclaimer}</p>}
              <p className="whitespace-pre-wrap rounded-xl bg-emerald-50 p-3 font-serif leading-relaxed dark:bg-emerald-500/10">{res.improved_text}</p>
              <div className="grid grid-cols-2 gap-2 text-xs">{Object.entries(res.scores).map(([k, v]) => <div key={k} className="flex justify-between rounded-lg bg-ink-50 px-2 py-1 dark:bg-ink-950"><span className="capitalize">{k.replace(/_/g, " ")}</span><b>{Math.round(v * 100)}%</b></div>)}</div>
              <div className="space-y-2">{res.issues.map((i, k) => (
                <div key={k} className="border-l-2 border-ink-200 pl-3 text-sm dark:border-ink-800">
                  <div className="flex flex-wrap items-center gap-2"><CategoryPill c={i.category} /><span className="text-rose-500 line-through">{i.original}</span>→<span className="text-emerald-600 dark:text-emerald-400">{i.corrected}</span></div>
                  <p className="text-ink-600 dark:text-ink-400">{i.explanation}</p>
                </div>))}</div>
              {res.repeated_words.length > 0 && <p className="text-sm"><span className="label inline">Repeated · </span>{res.repeated_words.join(", ")}</p>}
              {res.advanced_expressions.length > 0 && <div className="text-sm"><div className="label">Upgrade your expressions</div>{res.advanced_expressions.map((a) => <p key={a.try}>“{a.instead_of}” → <b>“{a.try}”</b></p>)}</div>}
              {res.next_exercise && <p className="rounded-xl bg-brand-50 p-3 text-sm text-brand-700 dark:bg-brand-500/10 dark:text-brand-100"><b>Next exercise:</b> {res.next_exercise}</p>}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
