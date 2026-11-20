import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../lib/api";
import { Recorder, speakLocal } from "../lib/speech";
import { useProfile } from "../App";
import { ErrorBox } from "../components/ui";
import { BarChart } from "../components/BarChart";
import { Item, useLinePlayer } from "./Listening";
import PaperRunner from "./Papers";

interface Q { key: string; id: string; prompt: string; options: string[] }
interface Exam {
  id: string; title: string; disclaimer: string;
  listening: { minutes: number; parts: (Omit<Item, "questions"> & { questions: Q[] })[] };
  reading: { minutes: number; passages: { id: string; title: string; body: string; questions: Q[] }[] };
  writing: { minutes: number; task1: { prompt: string; chart: { title: string; categories: string[]; series: { name: string; values: number[] }[] } }; task2: { prompt: string } };
  speaking: { part1: string[]; part2: { topic: string; points: string[] }; part3: string[] };
}
interface ObjResult { correct: number; total: number; band: number; review: { key: string; prompt: string; given: string; answer: string; correct: boolean; explanation: string }[] }
interface Summary { bands: Record<string, number>; overall: number; complete: boolean; weakest: string; recommendation: string; target_gap: Record<string, number>; disclaimer: string }
type Step = "intro" | "listening" | "reading" | "writing" | "speaking" | "report";
const STEPS: Step[] = ["listening", "reading", "writing", "speaking"];

function useCountdown(minutes: number, running: boolean, onEnd: () => void) {
  const [left, setLeft] = useState(minutes * 60);
  const end = useRef(onEnd); end.current = onEnd;
  useEffect(() => { setLeft(minutes * 60); }, [minutes]);
  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => setLeft((l) => { if (l <= 1) { clearInterval(t); end.current(); return 0; } return l - 1; }), 1000);
    return () => clearInterval(t);
  }, [running]);
  return left;
}
const fmt = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

function Timer({ left }: { left: number }) {
  return <span className={`rounded-lg px-3 py-1 font-mono text-sm ${left < 300 ? "bg-rose-100 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300" : "bg-ink-100 dark:bg-ink-800"}`}>⏱ {fmt(left)}</span>;
}

const TABS = [["ielts", "IELTS Academic"], ["toefl-2026-1", "TOEFL iBT (2026)"], ["cambridge-c1-1", "Cambridge C1 Advanced"], ["cambridge-c2-1", "Cambridge C2 Proficiency"]];

export default function ExamHub() {
  const [tab, setTab] = useState("ielts");
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div><h1 className="h1">IELTS, TOEFL & Cambridge</h1><p className="muted mt-1">Full practice papers with timed sections and estimated scores. All content is original and written for this app.</p></div>
      <div className="flex flex-wrap gap-1">{TABS.map(([k, l]) => <button key={k} className={tab === k ? "btn-primary" : "btn-ghost"} onClick={() => setTab(k)}>{l}</button>)}</div>
      {tab === "ielts" ? <IeltsMock /> : <PaperRunner key={tab} paperId={tab} />}
    </div>
  );
}

function IeltsMock() {
  const [exam, setExam] = useState<Exam | null>(null);
  const [step, setStep] = useState<Step>("intro");
  const [aid, setAid] = useState<number | null>(null);
  const [results, setResults] = useState<Record<string, { band: number }>>({});
  const [summary, setSummary] = useState<Summary | null>(null);
  const [history, setHistory] = useState<{ id: number; started_at: string; overall_band: number | null; bands: Record<string, number> | null }[]>([]);
  useEffect(() => { api.get<Exam>("/api/exam/exams/ielts-academic-1").then(setExam); api.get<typeof history>("/api/exam/attempts").then(setHistory); }, []);

  async function begin() { const r = await api.post<{ attempt_id: number }>("/api/exam/attempts", { exam_id: "ielts-academic-1" }); setAid(r.attempt_id); setStep("listening"); }
  function next(section: Step, r?: { band: number }) {
    if (r) setResults((x) => ({ ...x, [section]: r }));
    const i = STEPS.indexOf(section);
    if (i < STEPS.length - 1) setStep(STEPS[i + 1]); else finish();
  }
  async function finish() { setSummary(await api.post<Summary>(`/api/exam/attempts/${aid}/finish`)); setStep("report"); }

  if (!exam) return <div className="text-ink-400">Loading…</div>;
  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div><h2 className="font-serif text-xl">{exam.title}</h2><p className="muted mt-1">{exam.disclaimer}</p></div>
        {step !== "intro" && step !== "report" && <div className="flex gap-1 text-xs">{STEPS.map((s) => <span key={s} className={`pill capitalize ${s === step ? "bg-brand-600 text-white" : results[s] ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300" : "bg-ink-100 dark:bg-ink-800"}`}>{s}</span>)}</div>}
      </div>
      {step === "intro" && (
        <div className="space-y-4">
          <div className="card space-y-3">
            <h2 className="font-serif text-xl">Full IELTS Academic mock: about 2 h 45 min</h2>
            <ul className="list-disc space-y-1 pl-5 text-sm">
              <li><b>Listening</b> (30 min): 4 recordings, 16 questions. Each recording plays once, as in the real test.</li>
              <li><b>Reading</b> (60 min): 3 academic passages, 15 questions.</li>
              <li><b>Writing</b> (60 min): Task 1 (chart, 150+ words) and Task 2 (essay, 250+ words). Needs an AI key.</li>
              <li><b>Speaking</b> (11–14 min): Parts 1, 2 (1 min preparation, 2 min talk) and 3, recorded. Needs an OpenAI key.</li>
            </ul>
            <p className="text-xs text-gold-500">All bands are practice estimates calibrated to public IELTS descriptors and approximate raw-score tables. Official scores come only from IELTS test centres. You can skip any section; the report uses the sections you complete. The TOEFL iBT and Cambridge C1/C2 papers are in the tabs above. The passages and recordings in this mock are exclusive to it, so you won't have seen them in the modules.</p>
            <button className="btn-primary" onClick={begin}>Start the mock exam</button>
          </div>
          {history.length > 0 && <div className="card"><h2 className="mb-2 font-semibold">Previous attempts</h2><table className="w-full text-sm"><tbody>{history.map((h) => (
            <tr key={h.id} className="border-t border-ink-100 dark:border-ink-800"><td className="py-2">{new Date(h.started_at).toLocaleDateString()}</td><td className="text-ink-400">{h.bands ? Object.entries(h.bands).map(([k, v]) => `${k[0].toUpperCase()} ${v}`).join(" · ") : "unfinished"}</td><td className="text-right font-serif text-lg">{h.overall_band ?? "–"}</td></tr>))}</tbody></table></div>}
        </div>
      )}
      {step === "listening" && aid && <ObjectiveSection kind="listening" exam={exam} aid={aid} onDone={(r) => next("listening", r)} />}
      {step === "reading" && aid && <ObjectiveSection kind="reading" exam={exam} aid={aid} onDone={(r) => next("reading", r)} />}
      {step === "writing" && aid && <WritingSection exam={exam} aid={aid} onDone={(r) => next("writing", r)} />}
      {step === "speaking" && aid && <SpeakingSection exam={exam} aid={aid} onDone={(r) => next("speaking", r)} />}
      {step === "report" && summary && <Report s={summary} />}
    </div>
  );
}

function ListeningPart({ part, onPlayed }: { part: Exam["listening"]["parts"][number]; onPlayed: () => void }) {
  const [state, setState] = useState<"ready" | "playing" | "done">("ready");
  const [cur, setCur] = useState(-1);
  const player = useLinePlayer(part as unknown as Item, 1);
  useEffect(() => () => player.stop(), []); // eslint-disable-line
  return (
    <div className="flex items-center gap-3">
      {state === "ready" && <button className="btn-primary" onClick={async () => { setState("playing"); await player.playFrom(0, part.lines.length - 1, setCur); setState("done"); onPlayed(); }}>▶ Play recording (once only)</button>}
      {state === "playing" && <span className="text-sm text-brand-500">Playing… line {cur + 1}/{part.lines.length}</span>}
      {state === "done" && <span className="text-sm text-ink-400">Recording finished.</span>}
    </div>
  );
}

function ObjectiveSection({ kind, exam, aid, onDone }: { kind: "listening" | "reading"; exam: Exam; aid: number; onDone: (r: ObjResult) => void }) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [result, setResult] = useState<ObjResult | null>(null);
  const [page, setPage] = useState(0);
  const started = useRef(Date.now());
  const minutes = kind === "listening" ? exam.listening.minutes : exam.reading.minutes;
  const submit = async () => {
    if (result) return;
    setResult(await api.post<ObjResult>(`/api/exam/attempts/${aid}/objective`, { section: kind, answers, seconds: Math.round((Date.now() - started.current) / 1000) }));
  };
  const left = useCountdown(minutes, !result, submit);
  const groups = kind === "listening" ? exam.listening.parts : exam.reading.passages;
  const g = groups[page];

  if (result) return (
    <div className="card space-y-4">
      <div className="flex items-center justify-between"><h2 className="font-serif text-xl capitalize">{kind}: {result.correct}/{result.total}</h2><span className="font-serif text-3xl">Band ≈ {result.band}</span></div>
      <details><summary className="cursor-pointer text-sm text-brand-500">Review answers</summary>
        <ul className="mt-3 space-y-2 text-sm">{result.review.map((r) => <li key={r.key} className={r.correct ? "" : "text-rose-600 dark:text-rose-300"}>{r.correct ? "✓" : "✗"} {r.prompt} <span className="text-ink-400">→ {r.answer}. {r.explanation}</span></li>)}</ul></details>
      <button className="btn-primary" onClick={() => onDone(result)}>Continue to the next section</button>
    </div>
  );
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between"><h2 className="font-serif text-xl capitalize">{kind}: part {page + 1} of {groups.length}</h2><Timer left={left} /></div>
      <div className={kind === "reading" ? "grid grid-cols-2 gap-6" : "space-y-4"}>
        {kind === "listening"
          ? <div className="card"><div className="mb-2 font-medium">{g.title}</div><ListeningPart key={g.id} part={g as Exam["listening"]["parts"][number]} onPlayed={() => {}} /></div>
          : <div className="card max-h-[70vh] overflow-y-auto"><h3 className="mb-3 font-serif text-lg">{g.title}</h3><div className="space-y-3 font-serif leading-7">{(g as Exam["reading"]["passages"][number]).body.split("\n\n").map((p, i) => <p key={i}>{p}</p>)}</div></div>}
        <div className="card max-h-[70vh] space-y-5 overflow-y-auto">{g.questions.map((q, i) => (
          <div key={q.key}><div className="mb-2 text-sm font-medium">{i + 1}. {q.prompt}</div>
            <div className="grid gap-1.5">{q.options.map((o) => (
              <label key={o} className="flex cursor-pointer items-start gap-2 text-sm"><input type="radio" name={q.key} checked={answers[q.key] === o} onChange={() => setAnswers((a) => ({ ...a, [q.key]: o }))} className="mt-1" />{o}</label>))}</div></div>
        ))}</div>
      </div>
      <div className="flex justify-between">
        <button className="btn-ghost" disabled={page === 0} onClick={() => setPage(page - 1)}>← Previous part</button>
        {page < groups.length - 1 ? <button className="btn-primary" onClick={() => setPage(page + 1)}>Next part →</button>
          : <button className="btn-primary" onClick={submit}>Submit {kind}</button>}
      </div>
    </div>
  );
}

function WritingSection({ exam, aid, onDone }: { exam: Exam; aid: number; onDone: (r: { band: number }) => void }) {
  const [t1, setT1] = useState(""); const [t2, setT2] = useState("");
  const [busy, setBusy] = useState(false); const [err, setErr] = useState<string | null>(null);
  const [res, setRes] = useState<any>(null); // eslint-disable-line @typescript-eslint/no-explicit-any
  const started = useRef(Date.now());
  const submit = async () => {
    if (busy || res) return;
    setBusy(true); setErr(null);
    try { setRes(await api.post(`/api/exam/attempts/${aid}/writing`, { task1: t1, task2: t2, seconds: Math.round((Date.now() - started.current) / 1000) })); }
    catch (e) { setErr((e as ApiError).status === 412 ? "Writing assessment needs the AI professor to be set up (Settings › AI providers). You can skip this section." : (e as Error).message); } finally { setBusy(false); }
  };
  const left = useCountdown(exam.writing.minutes, !res, submit);
  const wc = (s: string) => (s.trim() ? s.trim().split(/\s+/).length : 0);
  if (res) return (
    <div className="card space-y-4">
      <div className="flex items-center justify-between"><h2 className="font-serif text-xl">Writing</h2><span className="font-serif text-3xl">Band ≈ {res.band}</span></div>
      {(["task1", "task2"] as const).map((t) => res[t] && (
        <div key={t} className="space-y-1 text-sm"><div className="label">{t === "task1" ? "Task 1" : "Task 2"} · band {res[t].band}</div>
          <p className="text-ink-400">{Object.entries(res[t]).filter(([k, v]) => typeof v === "number" && !["band", "word_count"].includes(k)).map(([k, v]) => `${k.replace(/_/g, " ")} ${v}`).join(" · ")}</p>
          <p>{res[t].feedback}</p>
          {(res[t].key_errors ?? []).map((e: { original: string; corrected: string; explanation: string }, i: number) => <p key={i}><span className="text-rose-500 line-through">{e.original}</span> → <span className="text-emerald-600">{e.corrected}</span> <span className="text-ink-400">{e.explanation}</span></p>)}
        </div>))}
      <button className="btn-primary" onClick={() => onDone(res)}>Continue to Speaking</button>
    </div>
  );
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between"><h2 className="font-serif text-xl">Writing</h2><Timer left={left} /></div>
      <div className="card space-y-3"><div className="label">Task 1 · suggested 20 minutes</div><p className="text-sm">{exam.writing.task1.prompt}</p>
        <div className="mx-auto max-w-2xl"><BarChart title={exam.writing.task1.chart.title} categories={exam.writing.task1.chart.categories} series={exam.writing.task1.chart.series} unit="%" /></div>
        <textarea className="input min-h-[200px] font-serif" value={t1} onChange={(e) => setT1(e.target.value)} /><div className={`text-xs ${wc(t1) < 150 ? "text-gold-500" : "text-ink-400"}`}>{wc(t1)} words</div></div>
      <div className="card space-y-3"><div className="label">Task 2 · suggested 40 minutes</div><p className="text-sm">{exam.writing.task2.prompt}</p>
        <textarea className="input min-h-[320px] font-serif" value={t2} onChange={(e) => setT2(e.target.value)} /><div className={`text-xs ${wc(t2) < 250 ? "text-gold-500" : "text-ink-400"}`}>{wc(t2)} words</div></div>
      <ErrorBox msg={err} />
      <div className="flex justify-between"><button className="btn-ghost" onClick={() => onDone(undefined as never)}>Skip writing</button><button className="btn-primary" disabled={busy || (wc(t1) + wc(t2)) < 40} onClick={submit}>{busy ? "The examiner is marking…" : "Submit writing"}</button></div>
    </div>
  );
}

function SpeakingSection({ exam, aid, onDone }: { exam: Exam; aid: number; onDone: (r: { band: number }) => void }) {
  const { profile } = useProfile();
  const [part, setPart] = useState(1);
  const [blobs, setBlobs] = useState<Record<number, Blob>>({});
  const [texts, setTexts] = useState<Record<number, { t: string; d: number }>>({});
  const [rec, setRec] = useState(false);
  const [prep, setPrep] = useState<number | null>(null);
  const [busy, setBusy] = useState(false); const [err, setErr] = useState<string | null>(null);
  const [res, setRes] = useState<any>(null); // eslint-disable-line @typescript-eslint/no-explicit-any
  const r = useRef(new Recorder());
  const autoStop = useRef<number>();
  const sp = exam.speaking;
  const say = (t: string) => speakLocal(t, profile.accent_preference);

  async function startRec(maxSec: number) {
    try { await r.current.start(profile.accent_preference); setRec(true); autoStop.current = window.setTimeout(stopRec, maxSec * 1000); }
    catch { setErr("Microphone not available."); }
  }
  async function stopRec() {
    window.clearTimeout(autoStop.current);
    const b = await r.current.stop(); setRec(false);
    setBlobs((x) => ({ ...x, [part]: b }));
    setTexts((x) => ({ ...x, [part]: { t: r.current.transcript, d: r.current.duration } }));
  }
  function startPrep() { setPrep(60); say(`Here is your topic. ${sp.part2.topic} You have one minute to prepare.`);
    const t = setInterval(() => setPrep((p) => { if (p == null || p <= 1) { clearInterval(t); say("Please begin speaking now."); startRec(120); return null; } return p - 1; }), 1000); }
  async function submit() {
    setBusy(true); setErr(null);
    const fd = new FormData();
    [1, 2, 3].forEach((k) => {
      fd.append(`part${k}`, blobs[k] ?? new Blob(), `part${k}.webm`);
      if (texts[k]?.t) { fd.append(`transcript_part${k}`, texts[k].t); fd.append(`duration_part${k}`, String(texts[k].d)); }
    });
    try { setRes(await api.upload(`/api/exam/attempts/${aid}/speaking`, fd)); }
    catch (e) { setErr((e as ApiError).status === 412 ? "Speaking assessment needs the AI professor to be set up (Settings › AI providers). You can skip this section." : (e as Error).message); } finally { setBusy(false); }
  }

  if (res) return (
    <div className="card space-y-3">
      <div className="flex items-center justify-between"><h2 className="font-serif text-xl">Speaking</h2><span className="font-serif text-3xl">Band ≈ {res.band}</span></div>
      <p className="text-sm text-ink-400">Fluency {res.fluency_coherence} · Lexis {res.lexical_resource} · Grammar {res.grammatical_range_accuracy} · Pronunciation {res.pronunciation} (estimated)</p>
      <p className="text-sm">{res.feedback}</p>
      {res.improvements?.length > 0 && <ul className="list-disc pl-5 text-sm">{res.improvements.map((x: string) => <li key={x}>{x}</li>)}</ul>}
      <button className="btn-primary" onClick={() => onDone(res)}>See my report</button>
    </div>
  );
  const questions = part === 1 ? sp.part1 : part === 3 ? sp.part3 : [];
  return (
    <div className="card space-y-4">
      <div className="flex items-center justify-between"><h2 className="font-serif text-xl">Speaking: Part {part}</h2>{blobs[part] && <span className="text-xs text-emerald-500">✓ recorded</span>}</div>
      {part !== 2 ? (
        <>
          <p className="muted">Start recording, then click each question to hear the examiner ask it, and answer naturally (2–4 sentences each).</p>
          <ol className="list-decimal space-y-2 pl-5">{questions.map((q) => <li key={q}><button className="text-left hover:text-brand-500" onClick={() => say(q)}>🔊 {q}</button></li>)}</ol>
          {!rec ? <button className="btn-primary" onClick={() => startRec(part === 1 ? 300 : 360)}>● {blobs[part] ? "Re-record" : "Start recording"}</button> : <button className="btn-primary animate-pulse !bg-rose-600" onClick={stopRec}>■ Stop</button>}
        </>
      ) : (
        <>
          <div className="rounded-xl border border-ink-200 p-4 dark:border-ink-800"><div className="font-medium">{sp.part2.topic}</div><div className="mt-1 text-sm text-ink-400">You should say:</div><ul className="list-disc pl-5 text-sm">{sp.part2.points.map((p) => <li key={p}>{p}</li>)}</ul></div>
          {prep != null ? <p className="font-mono text-lg">Preparation: {prep}s (make notes)</p>
            : rec ? <button className="btn-primary animate-pulse !bg-rose-600" onClick={stopRec}>■ Stop (auto-stops at 2 minutes)</button>
            : <button className="btn-primary" onClick={startPrep}>{blobs[2] ? "Redo Part 2" : "Start 1-minute preparation"}</button>}
        </>
      )}
      <ErrorBox msg={err} />
      <div className="flex justify-between border-t border-ink-100 pt-4 dark:border-ink-800">
        <button className="btn-ghost" onClick={() => onDone(undefined as never)}>Skip speaking</button>
        {part < 3 ? <button className="btn-primary" disabled={rec || prep != null} onClick={() => setPart(part + 1)}>Next part →</button>
          : <button className="btn-primary" disabled={busy || rec || !Object.keys(blobs).length} onClick={submit}>{busy ? "The examiner is assessing…" : "Submit speaking"}</button>}
      </div>
    </div>
  );
}

function Report({ s }: { s: Summary }) {
  return (
    <div className="space-y-4">
      <div className="card text-center"><div className="label">Overall band (practice estimate)</div><div className="font-serif text-6xl">{s.overall}</div>
        {!s.complete && <p className="mt-2 text-xs text-gold-500">Based only on the sections you completed.</p>}</div>
      <div className="grid grid-cols-4 gap-4">{["listening", "reading", "writing", "speaking"].map((k) => (
        <div key={k} className="card text-center"><div className="label">{k}</div><div className={`font-serif text-3xl ${s.bands[k] != null && s.bands[k] < 7 ? "text-gold-500" : ""}`}>{s.bands[k] ?? "–"}</div>
          {s.target_gap[k] != null && <div className="text-xs text-ink-400">{s.target_gap[k]} below the 7.0 target</div>}</div>))}</div>
      <div className="card"><div className="label">Priority: {s.weakest}</div><p>{s.recommendation}</p></div>
      <p className="text-xs text-gold-500">{s.disclaimer}</p>
      <Link to="/" className="btn-primary">Back to dashboard</Link>
    </div>
  );
}
