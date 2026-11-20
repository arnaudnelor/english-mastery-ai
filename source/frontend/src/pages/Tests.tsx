import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { LEVEL_NAMES } from "./Academy";
import { useAcademy } from "../App";
import { api, ApiError } from "../lib/api";
import { Recorder } from "../lib/speech";
import { useProfile } from "../App";
import { ErrorBox } from "../components/ui";
import { Item, useLinePlayer } from "./Listening";

interface Q { id: string; level?: string; prompt: string; options: string[]; key?: string }
interface Placement { grammar_vocab: Q[]; reading: { title: string; body: string; questions: Q[] }; listening: (Omit<Item, "questions"> & { questions: Q[] })[]; writing_prompt: string; speaking_prompt: string }
interface PlacementResult { overall: string; overall_name?: string; skills: Record<string, string>; scores: Record<string, number>; notes: string[]; disclaimer: string; writing: { justification: string } | null }

export default function Tests() {
  const [params] = useSearchParams();
  const [mode, setMode] = useState<"menu" | "placement" | "weekly">(params.get("start") === "placement" ? "placement" : "menu");
  useEffect(() => { if (params.get("start") === "placement") setMode("placement"); }, [params]);
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div><h1 className="h1">Tests & Assessments</h1><p className="muted mt-1">Placement test, weekly progress checks and full mock exams.</p></div>
      {mode === "menu" && (
        <div className="grid grid-cols-3 gap-4">
          <button className="card text-left hover:border-brand-400" onClick={() => setMode("placement")}><div className="text-3xl">🧭</div><div className="mt-2 font-serif text-lg">Placement test</div><p className="muted mt-1">About 40 minutes, four skills. Sets your CEFR level and your learning path. Retake it monthly.</p></button>
          <button className="card text-left hover:border-brand-400" onClick={() => setMode("weekly")}><div className="text-3xl">✅</div><div className="mt-2 font-serif text-lg">Weekly check</div><p className="muted mt-1">12 questions on your recurring mistakes and your flashcard words. About 8 minutes.</p></button>
          <Link to="/exams" className="card hover:border-brand-400"><div className="text-3xl">🎓</div><div className="mt-2 font-serif text-lg">Monthly mock exam</div><p className="muted mt-1">Full IELTS Academic practice test with estimated band scores.</p></Link>
        </div>
      )}
      {mode === "placement" && <PlacementTest onExit={() => setMode("menu")} />}
      {mode === "weekly" && <Weekly onExit={() => setMode("menu")} />}
    </div>
  );
}

function Choice({ q, value, onChange }: { q: Q; value?: string; onChange: (v: string) => void }) {
  return (
    <div><div className="mb-2 text-sm font-medium">{q.prompt}</div>
      <div className="grid grid-cols-2 gap-1.5">{q.options.map((o) => <label key={o} className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-1.5 text-sm ${value === o ? "border-brand-500 bg-brand-50 dark:bg-brand-500/10" : "border-ink-200 dark:border-ink-800"}`}><input type="radio" className="hidden" checked={value === o} onChange={() => onChange(o)} />{o}</label>)}</div></div>
  );
}

function PlayOnce({ item }: { item: Placement["listening"][number] }) {
  const [state, setState] = useState<"ready" | "playing" | "done">("ready");
  const player = useLinePlayer(item as unknown as Item, 1);
  useEffect(() => () => player.stop(), []); // eslint-disable-line
  return state === "ready" ? <button className="btn-primary" onClick={async () => { setState("playing"); await player.playFrom(0, item.lines.length - 1, () => {}); setState("done"); }}>▶ Play “{item.title}” (once)</button>
    : <span className="text-sm text-ink-400">{state === "playing" ? "Playing…" : "Finished"}</span>;
}

function PlacementTest({ onExit }: { onExit: () => void }) {
  const { profile, setProfile } = useProfile();
  const { reload } = useAcademy();
  const [t, setT] = useState<Placement | null>(null);
  const [step, setStep] = useState(0);
  const [ans, setAns] = useState<Record<string, string>>({});
  const [writing, setWriting] = useState("");
  const [speak, setSpeak] = useState<{ level: string; justification: string } | null>(null);
  const [rec, setRec] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [res, setRes] = useState<PlacementResult | null>(null);
  const r = useRef(new Recorder());
  const started = useRef(Date.now());
  useEffect(() => { api.get<Placement>("/api/assess/placement").then(setT); }, []);
  if (!t) return <div className="text-ink-400">Loading…</div>;
  const set = (k: string, v: string) => setAns((a) => ({ ...a, [k]: v }));
  const STEPS = ["Grammar, vocabulary & sentences", "Reading", "Listening", "Writing", "Speaking"];

  async function stopSpeaking() {
    setRec(false); setBusy(true); setErr(null);
    const fd = new FormData(); fd.append("audio", await r.current.stop(), "speech.webm"); r.current.attach(fd);
    try { setSpeak(await api.upload("/api/assess/placement/speaking", fd)); }
    catch (e) { setErr((e as ApiError).status === 412 ? "Speaking assessment needs the AI professor to be set up (Settings). You can skip this part." : (e as Error).message); } finally { setBusy(false); }
  }
  async function submit() {
    setBusy(true);
    try {
      const out = await api.post<PlacementResult>("/api/assess/placement/submit", { answers: ans, writing, speaking_level: speak?.level ?? null, seconds: Math.round((Date.now() - started.current) / 1000) });
      setRes(out);
      setProfile(await api.get("/api/profile"));
      reload();
    } finally { setBusy(false); }
  }

  if (res) return (
    <div className="space-y-4">
      <div className="card text-center !border-brand-500"><div className="label">Your English level</div><div className="font-serif text-5xl">{res.overall} — {(res.overall_name ?? LEVEL_NAMES[res.overall]).toUpperCase()}</div>
        <p className="mt-2 text-sm">Your {res.overall} programme is now open, and every level below it stays available for review.</p><p className="mt-2 text-xs text-gold-500">{res.disclaimer}</p></div>
      <div className="grid grid-cols-5 gap-3">{Object.entries(res.skills).map(([k, v]) => <div key={k} className="card text-center"><div className="label">{k.replace("_", " & ")}</div><div className="font-serif text-2xl">{v}</div>{res.scores[k] != null && <div className="text-xs text-ink-400">{Math.round(res.scores[k] * 100)}%</div>}</div>)}</div>
      {res.writing?.justification && <div className="card text-sm"><div className="label">Writing</div>{res.writing.justification}</div>}
      {res.notes.length > 0 && <ul className="list-disc pl-5 text-sm text-ink-400">{res.notes.map((n) => <li key={n}>{n}</li>)}</ul>}
      <div className="flex gap-2"><Link to={`/level/${res.overall}`} className="btn-primary">Start my {res.overall} programme</Link><Link to="/" className="btn-ghost">Dashboard</Link><button className="btn-ghost" onClick={onExit}>Back</button></div>
    </div>
  );
  return (
    <div className="space-y-4">
      <div className="flex gap-1">{STEPS.map((s, i) => <span key={s} className={`pill ${i === step ? "bg-brand-600 text-white" : i < step ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300" : "bg-ink-100 dark:bg-ink-800"}`}>{i + 1}. {s}</span>)}</div>
      <div className="card space-y-5">
        {step === 0 && t.grammar_vocab.map((q, i) => <Choice key={q.id} q={{ ...q, prompt: `${i + 1}. ${q.prompt}` }} value={ans[q.id]} onChange={(v) => set(q.id, v)} />)}
        {step === 1 && <><h2 className="font-serif text-xl">{t.reading.title}</h2><div className="space-y-3 font-serif leading-7">{t.reading.body.split("\n\n").map((p, i) => <p key={i}>{p}</p>)}</div>{t.reading.questions.map((q) => <Choice key={q.key} q={q} value={ans[q.key!]} onChange={(v) => set(q.key!, v)} />)}</>}
        {step === 2 && t.listening.map((it) => <div key={it.id} className="space-y-3 border-b border-ink-100 pb-4 dark:border-ink-800"><PlayOnce item={it} />{it.questions.map((q) => <Choice key={q.key} q={q} value={ans[q.key!]} onChange={(v) => set(q.key!, v)} />)}</div>)}
        {step === 3 && <><p>{t.writing_prompt}</p><textarea className="input min-h-[220px] font-serif" value={writing} onChange={(e) => setWriting(e.target.value)} /><p className="text-xs text-ink-400">{writing.trim() ? writing.trim().split(/\s+/).length : 0} words · assessed by AI if a key is configured, otherwise skipped</p></>}
        {step === 4 && <><p>{t.speaking_prompt}</p>
          {!rec ? <button className="btn-primary" disabled={busy} onClick={async () => { try { await r.current.start(profile.accent_preference); setRec(true); } catch { setErr("Microphone not available."); } }}>● {speak ? "Record again" : "Start recording"}</button>
            : <button className="btn-primary animate-pulse !bg-rose-600" onClick={stopSpeaking}>■ Stop</button>}
          {busy && <p className="text-sm text-ink-400">Assessing…</p>}
          {speak && <p className="text-sm">Speaking level: <b>{speak.level}</b> — {speak.justification}</p>}
          <ErrorBox msg={err} /></>}
      </div>
      <div className="flex justify-between">
        <button className="btn-ghost" onClick={() => (step ? setStep(step - 1) : onExit())}>← {step ? "Back" : "Cancel"}</button>
        {step < 4 ? <button className="btn-primary" onClick={() => setStep(step + 1)}>Next →</button> : <button className="btn-primary" disabled={busy || rec} onClick={submit}>See my level</button>}
      </div>
    </div>
  );
}

function Weekly({ onExit }: { onExit: () => void }) {
  const [items, setItems] = useState<{ key: string; kind: string; type: string; prompt: string; options: string[] | null; topic?: string }[]>([]);
  const [ans, setAns] = useState<Record<string, string>>({});
  const [res, setRes] = useState<{ score: number; review: { key: string; correct: boolean; answer: string; explanation: string }[] } | null>(null);
  useEffect(() => { api.get<{ items: typeof items }>("/api/assess/weekly").then((r) => setItems(r.items)); }, []);
  const review = (k: string) => res?.review.find((r) => r.key === k);
  return (
    <div className="space-y-4">
      <div className="card space-y-5">{items.map((q, i) => {
        const rv = review(q.key);
        return (
          <div key={q.key}>
            {q.options ? <Choice q={{ id: q.key, prompt: `${i + 1}. ${q.prompt}`, options: q.options }} value={ans[q.key]} onChange={(v) => !res && setAns((a) => ({ ...a, [q.key]: v }))} />
              : <div><div className="mb-2 text-sm font-medium">{i + 1}. {q.prompt}</div><input className="input" disabled={!!res} value={ans[q.key] ?? ""} onChange={(e) => setAns((a) => ({ ...a, [q.key]: e.target.value }))} /></div>}
            {q.topic && <div className="mt-1 text-xs text-ink-400">{q.topic}</div>}
            {rv && <p className={`mt-1 text-sm ${rv.correct ? "text-emerald-600" : "text-rose-600 dark:text-rose-300"}`}>{rv.correct ? "✓" : `✗ ${rv.answer}`} <span className="text-ink-400">{rv.explanation}</span></p>}
          </div>
        );
      })}</div>
      {res ? <div className="card flex items-center justify-between"><span className="font-serif text-2xl">{Math.round(res.score * 100)}%</span><button className="btn-ghost" onClick={onExit}>Done</button></div>
        : <div className="flex justify-between"><button className="btn-ghost" onClick={onExit}>Cancel</button><button className="btn-primary" disabled={Object.keys(ans).length < items.length} onClick={async () => setRes(await api.post("/api/assess/weekly/submit", { answers: ans }))}>Submit</button></div>}
    </div>
  );
}
