import { Fragment, useEffect, useRef, useState } from "react";
import { api, ApiError } from "../lib/api";
import { playLine, Recorder, speakLocal } from "../lib/speech";
import { useProfile } from "../App";
import { ErrorBox } from "../components/ui";
import { Item, useLinePlayer } from "./Listening";

interface Gap { options?: string[]; hint?: string; prefix?: string }
interface Question { id: string; prompt: string; options: string[]; say?: string; voice?: string; accent?: string }
interface Part {
  id: string; type: "gapfill" | "mcq" | "transform" | "build_sentence" | "writing" | "speaking_repeat" | "speaking_answer";
  title: string; instructions?: string; text?: string; gaps?: Record<string, Gap>; passage?: string;
  audio?: { speakers: Item["speakers"]; lines: Item["lines"] }; questions?: Question[];
  items?: { id: string; first?: string; key?: string; before?: string; after?: string; context?: string; chunks?: string[]; text?: string; question?: string }[];
  tasks?: { id: string; label: string; prompt: string; min_words: number }[];
}
interface Section { id: string; name: string; minutes: number; scoring: "objective" | "writing" | "speaking"; parts: Part[] }
interface Paper { id: string; kind: string; title: string; intro: string; disclaimer: string; sections: Section[] }
interface Summary { sections: Record<string, number>; overall: number; scale: string; result: string; complete: boolean; weakest: string; disclaimer: string }

const fmt = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

function Countdown({ minutes, onEnd, running }: { minutes: number; onEnd: () => void; running: boolean }) {
  const [left, setLeft] = useState(minutes * 60);
  const cb = useRef(onEnd); cb.current = onEnd;
  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => setLeft((l) => { if (l <= 1) { clearInterval(t); cb.current(); return 0; } return l - 1; }), 1000);
    return () => clearInterval(t);
  }, [running]);
  return <span className={`rounded-lg px-3 py-1 font-mono text-sm ${left < 300 ? "bg-rose-100 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300" : "bg-ink-100 dark:bg-ink-800"}`}>⏱ {fmt(left)}</span>;
}

export default function PaperRunner({ paperId }: { paperId: string }) {
  const [paper, setPaper] = useState<Paper | null>(null);
  const [aid, setAid] = useState<number | null>(null);
  const [idx, setIdx] = useState(-1);
  const [scores, setScores] = useState<Record<string, number | string>>({});
  const [summary, setSummary] = useState<Summary | null>(null);
  useEffect(() => { setPaper(null); setAid(null); setIdx(-1); setSummary(null); setScores({}); api.get<Paper>(`/api/papers/${paperId}`).then(setPaper); }, [paperId]);
  if (!paper) return <div className="text-ink-400">Loading…</div>;

  async function begin() { const r = await api.post<{ attempt_id: number }>(`/api/papers/${paperId}/attempts`); setAid(r.attempt_id); setIdx(0); }
  async function next(score?: number) {
    if (score !== undefined) setScores((s) => ({ ...s, [paper!.sections[idx].id]: score }));
    if (idx < paper!.sections.length - 1) setIdx(idx + 1);
    else {
      try { setSummary(await api.post<Summary>(`/api/papers/${paperId}/attempts/${aid}/finish`)); } catch { setSummary(null); }
      setIdx(paper!.sections.length);
    }
  }

  if (idx === -1) return (
    <div className="card space-y-3">
      <h2 className="font-serif text-xl">{paper.title}</h2>
      <p className="text-sm">{paper.intro}</p>
      <ul className="list-disc pl-5 text-sm">{paper.sections.map((s) => <li key={s.id}><b>{s.name}</b> — {s.minutes} min{s.scoring !== "objective" ? " (AI-assessed, needs an API key; can be skipped)" : ""}</li>)}</ul>
      <p className="text-xs text-gold-500">{paper.disclaimer}</p>
      <button className="btn-primary" onClick={begin}>Start</button>
    </div>
  );
  if (idx >= paper.sections.length) return (
    <div className="space-y-4">
      {summary ? <>
        <div className="card text-center"><div className="label">{summary.scale} (practice estimate)</div><div className="font-serif text-6xl">{summary.overall}</div><div className="mt-1 text-lg">{summary.result}</div>
          {!summary.complete && <p className="mt-2 text-xs text-gold-500">Based on the sections you completed.</p>}</div>
        <div className="grid grid-cols-4 gap-3">{paper.sections.map((s) => <div key={s.id} className="card text-center"><div className="label">{s.name}</div><div className="font-serif text-2xl">{summary.sections[s.id] ?? "–"}</div></div>)}</div>
        <div className="card text-sm">Priority area: <b>{paper.sections.find((s) => s.id === summary.weakest)?.name}</b>. Practise it in the matching module, then retake this paper in a few weeks.</div>
        <p className="text-xs text-gold-500">{summary.disclaimer}</p>
      </> : <div className="card">No section was completed.</div>}
    </div>
  );
  const sec = paper.sections[idx];
  return (
    <div className="space-y-4">
      <div className="flex gap-1 text-xs">{paper.sections.map((s, i) => <span key={s.id} className={`pill ${i === idx ? "bg-brand-600 text-white" : scores[s.id] !== undefined ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300" : "bg-ink-100 dark:bg-ink-800"}`}>{s.name}</span>)}</div>
      {sec.scoring === "objective" && <ObjectiveSection key={sec.id} paper={paper} sec={sec} aid={aid!} onDone={next} />}
      {sec.scoring === "writing" && <WritingSection key={sec.id} paper={paper} sec={sec} aid={aid!} onDone={next} />}
      {sec.scoring === "speaking" && <SpeakingSection key={sec.id} paper={paper} sec={sec} aid={aid!} onDone={next} />}
    </div>
  );
}

// ------------------------------------------------------------------ parts
function GapText({ part, ans, set, review }: { part: Part; ans: Record<string, string>; set: (k: string, v: string) => void; review?: Record<string, { correct: boolean; answer: string }> }) {
  const bits = part.text!.split(/\{(\d+)\}/);
  return (
    <p className="font-serif leading-[2.6rem]">{bits.map((b, i) => {
      if (i % 2 === 0) return <Fragment key={i}>{b}</Fragment>;
      const g = part.gaps![b]; const key = `${part.id}:${b}`; const r = review?.[key];
      const cls = `input !inline-block !w-auto !py-0.5 !px-2 text-sm ${r ? (r.correct ? "!border-emerald-500" : "!border-rose-500") : ""}`;
      return (
        <span key={i} className="mx-0.5 whitespace-nowrap">
          <sup className="mr-0.5 text-[10px] text-ink-400">{b}</sup>
          {g.prefix && <b>{g.prefix}</b>}
          {g.options ? <select className={cls} value={ans[key] ?? ""} disabled={!!review} onChange={(e) => set(key, e.target.value)}><option value="">…</option>{g.options.map((o) => <option key={o}>{o}</option>)}</select>
            : <input className={`${cls} ${g.prefix ? "!w-24" : "!w-36"}`} value={ans[key] ?? ""} disabled={!!review} onChange={(e) => set(key, e.target.value)} />}
          {g.hint && <span className="ml-1 text-xs font-semibold text-gold-500">({g.hint})</span>}
          {r && !r.correct && <span className="ml-1 text-xs text-emerald-600">{r.answer}</span>}
        </span>
      );
    })}</p>
  );
}

function AudioBlock({ part }: { part: Part }) {
  const [state, setState] = useState<"ready" | "playing" | "done">("ready");
  const item = { id: part.id, speakers: part.audio!.speakers, lines: part.audio!.lines } as unknown as Item;
  const player = useLinePlayer(item, 1);
  useEffect(() => () => player.stop(), []); // eslint-disable-line
  return state === "ready" ? <button className="btn-primary" onClick={async () => { setState("playing"); await player.playFrom(0, part.audio!.lines.length - 1, () => {}); setState("done"); }}>▶ Play the recording (once)</button>
    : <span className="text-sm text-ink-400">{state === "playing" ? "Playing…" : "Recording finished."}</span>;
}

function SayButton({ q }: { q: Question }) {
  const [used, setUsed] = useState(false);
  return <button className="btn-ghost !py-1 text-xs" disabled={used} onClick={() => { setUsed(true); playLine(q.say!, q.voice ?? "alloy", q.accent ?? "en-US"); }}>{used ? "Played" : "▶ Listen (once)"}</button>;
}

function ObjectiveSection({ paper, sec, aid, onDone }: { paper: Paper; sec: Section; aid: number; onDone: (score?: number) => void }) {
  const [ans, setAns] = useState<Record<string, string>>({});
  const [res, setRes] = useState<{ pct: number; correct: number; total: number; score: number; review: { key: string; correct: boolean; answer: string; explanation?: string }[] } | null>(null);
  const started = useRef(Date.now());
  const set = (k: string, v: string) => setAns((a) => ({ ...a, [k]: v }));
  const submit = async () => { if (!res) setRes(await api.post(`/api/papers/${paper.id}/attempts/${aid}/sections/${sec.id}/objective`, { answers: ans, seconds: Math.round((Date.now() - started.current) / 1000) })); };
  const review = res ? Object.fromEntries(res.review.map((r) => [r.key, r])) : undefined;
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between"><h2 className="font-serif text-xl">{sec.name}</h2>{!res ? <Countdown minutes={sec.minutes} running onEnd={submit} /> : <span className="font-serif text-2xl">{res.correct}/{res.total} · {res.score}</span>}</div>
      {sec.parts.map((part) => (
        <div key={part.id} className="card space-y-4">
          <div><div className="font-semibold">{part.title}</div>{part.instructions && <p className="muted">{part.instructions}</p>}</div>
          {part.type === "gapfill" && <GapText part={part} ans={ans} set={set} review={review} />}
          {part.type === "transform" && part.items!.map((it, i) => {
            const key = `${part.id}:${it.id}`; const r = review?.[key];
            return (
              <div key={it.id} className="space-y-1 text-sm">
                <div>{i + 1}. {it.first}</div>
                <div className="flex flex-wrap items-center gap-2"><span className="rounded bg-gold-400/20 px-2 font-bold text-gold-500">{it.key}</span>{it.before}
                  <input className={`input !w-72 !py-1 ${r ? (r.correct ? "!border-emerald-500" : "!border-rose-500") : ""}`} disabled={!!res} value={ans[key] ?? ""} onChange={(e) => set(key, e.target.value)} />{it.after}</div>
                {r && !r.correct && <div className="text-xs text-emerald-600">Answer: {r.answer}</div>}
              </div>
            );
          })}
          {part.type === "mcq" && <>
            {part.passage && <div className="max-h-96 space-y-3 overflow-y-auto rounded-xl bg-ink-50 p-4 font-serif leading-7 dark:bg-ink-950">{part.passage.split("\n").filter(Boolean).map((p, i) => <p key={i}>{p}</p>)}</div>}
            {part.audio && <AudioBlock part={part} />}
            {part.questions!.map((q, i) => {
              const key = `${part.id}:${q.id}`; const r = review?.[key];
              return (
                <div key={q.id}>
                  <div className="mb-2 flex items-center gap-2 text-sm font-medium">{i + 1}. {q.say && <SayButton q={q} />} {q.prompt}</div>
                  <div className="grid grid-cols-2 gap-1.5">{q.options.map((o) => (
                    <label key={o} className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-1.5 text-sm ${r && o === r.answer ? "border-emerald-500" : ans[key] === o ? (r ? "border-rose-500" : "border-brand-500 bg-brand-50 dark:bg-brand-500/10") : "border-ink-200 dark:border-ink-800"}`}>
                      <input type="radio" className="hidden" disabled={!!res} checked={ans[key] === o} onChange={() => set(key, o)} />{o}</label>))}</div>
                  {r?.explanation && <p className="mt-1 text-xs text-ink-400">{r.explanation}</p>}
                </div>
              );
            })}
          </>}
        </div>
      ))}
      {!res ? <div className="flex justify-end"><button className="btn-primary" onClick={submit}>Submit {sec.name}</button></div>
        : <div className="flex justify-end"><button className="btn-primary" onClick={() => onDone(res.score)}>Continue</button></div>}
    </div>
  );
}

function BuildSentence({ part, ans, set }: { part: Part; ans: Record<string, string>; set: (k: string, v: string) => void }) {
  return <>{part.items!.map((it, i) => {
    const key = `${part.id}:${it.id}`;
    const chosen = (ans[key] ?? "").split(" ").filter(Boolean);
    const remaining = [...it.chunks!];
    chosen.forEach((c) => { const k = remaining.indexOf(c); if (k >= 0) remaining.splice(k, 1); });
    return (
      <div key={it.id} className="space-y-2 text-sm">
        <div className="text-ink-400">{i + 1}. “{it.context}”</div>
        <div className="min-h-[38px] rounded-lg border border-dashed border-ink-200 px-3 py-2 dark:border-ink-800">{chosen.join(" ") || <span className="text-ink-400">Click the words in order…</span>}</div>
        <div className="flex flex-wrap gap-1.5">{remaining.map((c, k) => <button key={c + k} className="chip !normal-case" onClick={() => set(key, [...chosen, c].join(" "))}>{c}</button>)}
          {chosen.length > 0 && <button className="text-xs text-rose-500" onClick={() => set(key, "")}>reset</button>}</div>
      </div>
    );
  })}</>;
}

function WritingSection({ paper, sec, aid, onDone }: { paper: Paper; sec: Section; aid: number; onDone: (score?: number) => void }) {
  const [ans, setAns] = useState<Record<string, string>>({});
  const [texts, setTexts] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false); const [err, setErr] = useState<string | null>(null);
  const [res, setRes] = useState<any>(null); // eslint-disable-line @typescript-eslint/no-explicit-any
  const started = useRef(Date.now());
  const wc = (s?: string) => (s?.trim() ? s.trim().split(/\s+/).length : 0);
  const submit = async () => {
    if (busy || res) return;
    setBusy(true); setErr(null);
    try { setRes(await api.post(`/api/papers/${paper.id}/attempts/${aid}/sections/${sec.id}/writing`, { texts, answers: ans, seconds: Math.round((Date.now() - started.current) / 1000) })); }
    catch (e) { setErr((e as ApiError).status === 412 ? "Writing assessment needs the AI professor to be set up (Settings › AI providers). You can skip this section." : (e as Error).message); } finally { setBusy(false); }
  };
  if (res) return (
    <div className="card space-y-3">
      <div className="flex items-center justify-between"><h2 className="font-serif text-xl">{sec.name}</h2><span className="font-serif text-3xl">{res.score}</span></div>
      {Object.entries(res.tasks ?? {}).map(([k, t]: [string, any]) => ( // eslint-disable-line @typescript-eslint/no-explicit-any
        <div key={k} className="text-sm"><div className="label">{k} · {t.score}/5</div><p>{t.feedback}</p>
          {(t.key_errors ?? []).map((e: { original: string; corrected: string; explanation: string }, i: number) => <p key={i}><span className="text-rose-500 line-through">{e.original}</span> → <span className="text-emerald-600">{e.corrected}</span> <span className="text-ink-400">{e.explanation}</span></p>)}</div>))}
      {res.objective_review?.length > 0 && <p className="text-sm">Build a Sentence: {res.objective_review.filter((r: { correct: boolean }) => r.correct).length}/{res.objective_review.length}</p>}
      <button className="btn-primary" onClick={() => onDone(res.score)}>Continue</button>
    </div>
  );
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between"><h2 className="font-serif text-xl">{sec.name}</h2><Countdown minutes={sec.minutes} running onEnd={submit} /></div>
      {sec.parts.map((part) => (
        <div key={part.id} className="card space-y-4">
          <div className="font-semibold">{part.title}</div>{part.instructions && <p className="muted">{part.instructions}</p>}
          {part.type === "build_sentence" && <BuildSentence part={part} ans={ans} set={(k, v) => setAns((a) => ({ ...a, [k]: v }))} />}
          {part.type === "writing" && part.tasks!.map((t) => (
            <div key={t.id} className="space-y-2"><div className="label">{t.label}</div><p className="whitespace-pre-line text-sm">{t.prompt}</p>
              <textarea className="input min-h-[220px] font-serif" value={texts[t.id] ?? ""} onChange={(e) => setTexts((x) => ({ ...x, [t.id]: e.target.value }))} />
              <div className={`text-xs ${wc(texts[t.id]) < t.min_words ? "text-gold-500" : "text-ink-400"}`}>{wc(texts[t.id])} words (minimum {t.min_words})</div></div>
          ))}
        </div>
      ))}
      <ErrorBox msg={err} />
      <div className="flex justify-between"><button className="btn-ghost" onClick={() => onDone()}>Skip this section</button><button className="btn-primary" disabled={busy} onClick={submit}>{busy ? "The examiner is marking…" : "Submit writing"}</button></div>
    </div>
  );
}

function SpeakingSection({ paper, sec, aid, onDone }: { paper: Paper; sec: Section; aid: number; onDone: (score?: number) => void }) {
  const { profile } = useProfile();
  const [blobs, setBlobs] = useState<Record<string, Blob>>({});
  const [texts, setTexts] = useState<Record<string, { t: string; d: number }>>({});
  const [recKey, setRecKey] = useState<string | null>(null);
  const [busy, setBusy] = useState(false); const [err, setErr] = useState<string | null>(null);
  const [res, setRes] = useState<any>(null); // eslint-disable-line @typescript-eslint/no-explicit-any
  const r = useRef(new Recorder());
  async function toggle(key: string) {
    setErr(null);
    if (recKey === key) {
      const b = await r.current.stop();
      setBlobs((x) => ({ ...x, [key]: b }));
      setTexts((x) => ({ ...x, [key]: { t: r.current.transcript, d: r.current.duration } }));
      setRecKey(null); return;
    }
    if (recKey) return;
    try { await r.current.start(profile.accent_preference); setRecKey(key); } catch { setErr("Microphone not available."); }
  }
  async function submit() {
    setBusy(true); setErr(null);
    const fd = new FormData();
    Object.entries(blobs).forEach(([k, b]) => {
      fd.append(k, b, `${k.replace(":", "_")}.webm`);
      if (texts[k]?.t) { fd.append(`transcript:${k}`, texts[k].t); fd.append(`duration:${k}`, String(texts[k].d)); }
    });
    try { setRes(await api.upload(`/api/papers/${paper.id}/attempts/${aid}/sections/${sec.id}/speaking`, fd)); }
    catch (e) { setErr((e as ApiError).status === 412 ? "Speaking assessment needs the AI professor to be set up (Settings › AI providers). You can skip this section." : (e as Error).message); } finally { setBusy(false); }
  }
  if (res) return (
    <div className="card space-y-3">
      <div className="flex items-center justify-between"><h2 className="font-serif text-xl">{sec.name}</h2><span className="font-serif text-3xl">{res.score}</span></div>
      {res.repeat?.length > 0 && <div className="text-sm"><div className="label">Listen and Repeat</div>{res.repeat.map((x: { id: string; target: string; heard: string; score: number }) => <p key={x.id}>{Math.round(x.score * 100)}% · <span className="text-ink-400">heard: “{x.heard}”</span></p>)}</div>}
      {res.assessment && <div className="text-sm"><p>{res.assessment.feedback}</p><ul className="list-disc pl-5">{(res.assessment.improvements ?? []).map((x: string) => <li key={x}>{x}</li>)}</ul></div>}
      <button className="btn-primary" onClick={() => onDone(res.score)}>Continue</button>
    </div>
  );
  const RecBtn = ({ k }: { k: string }) => <button className={recKey === k ? "btn-primary animate-pulse !bg-rose-600 !py-1" : "btn-ghost !py-1"} disabled={!!recKey && recKey !== k} onClick={() => toggle(k)}>{recKey === k ? "■ Stop" : blobs[k] ? "● Re-record" : "● Record"}</button>;
  return (
    <div className="space-y-4">
      <h2 className="font-serif text-xl">{sec.name}</h2>
      {sec.parts.map((part) => (
        <div key={part.id} className="card space-y-3">
          <div className="font-semibold">{part.title}</div>{part.instructions && <p className="muted">{part.instructions}</p>}
          {part.items!.map((it, i) => {
            const k = `${part.id}:${it.id}`;
            return (
              <div key={it.id} className="flex items-center justify-between gap-3 border-t border-ink-100 pt-3 text-sm dark:border-ink-800">
                <span>{i + 1}. {part.type === "speaking_repeat" ? <button className="btn-ghost !py-1" onClick={() => speakLocal(it.text!, profile.accent_preference, 0.95)}>▶ Hear sentence {i + 1}</button> : <button className="text-left hover:text-brand-500" onClick={() => speakLocal(it.question!, profile.accent_preference)}>🔊 {it.question}</button>}</span>
                <span className="flex items-center gap-2">{blobs[k] && <span className="text-xs text-emerald-500">✓</span>}<RecBtn k={k} /></span>
              </div>
            );
          })}
        </div>
      ))}
      <ErrorBox msg={err} />
      <div className="flex justify-between"><button className="btn-ghost" onClick={() => onDone()}>Skip this section</button><button className="btn-primary" disabled={busy || !!recKey || !Object.keys(blobs).length} onClick={submit}>{busy ? "Assessing…" : "Submit speaking"}</button></div>
    </div>
  );
}
