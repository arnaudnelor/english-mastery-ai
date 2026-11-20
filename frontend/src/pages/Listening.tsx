import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../lib/api";
import { audioUrl, stopAudio } from "../lib/speech";
import { playableUrl } from "../lib/preview";
import { ErrorBox, LevelPill } from "../components/ui";
import { BookmarkButton } from "../components/Bookmark";

interface ItemSummary { id: string; title: string; level: string; kind: string; domain: string; accents: string[]; lines: number }
interface Line { s: string; t: string }
export interface Item extends Omit<ItemSummary, "lines"> {
  speakers: Record<string, { accent: string; voice: string }>; lines: Line[]; questions: { id: string; prompt: string; options: string[] }[];
  dictation: number[]; gaps: { line: number; count: number; words: string[] }[]; expressions: { phrase: string; meaning: string }[]; audio_cached: boolean;
}
interface AlignWord { word: string | null; status: "ok" | "wrong" | "missed" | "extra"; heard?: string | null }


export const ACCENT_NAME: Record<string, string> = { "en-CA": "Canadian", "en-US": "American", "en-GB": "British" };
const SPEEDS = [0.75, 0.9, 1, 1.15];

export function ListeningList() {
  const [items, setItems] = useState<ItemSummary[]>([]);
  useEffect(() => { api.get<ItemSummary[]>("/api/listening/items").then(setItems); }, []);
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div><h1 className="h1">Listening Laboratory</h1><p className="muted mt-1">Original conversations, meetings, lectures, news and podcasts in Canadian, American and British English. Adjustable speed, transcripts, dictation and gap-fill.</p></div>
      <div className="grid grid-cols-2 gap-4">
        {items.map((it) => (
          <Link key={it.id} to={`/listening/${it.id}`} className="card transition hover:border-brand-400">
            <div className="flex items-center justify-between"><span className="text-xs uppercase tracking-wide text-ink-400">{it.kind}</span><LevelPill l={it.level} /></div>
            <div className="mt-2 font-serif text-lg">{it.title}</div>
            <div className="mt-3 text-xs text-ink-400">{it.accents.map((a) => ACCENT_NAME[a]).join(" · ")} · {it.lines} turns</div>
          </Link>
        ))}
      </div>
    </div>
  );
}

/** Plays one line: cached/AI audio from the engine, or a Windows voice if no key. */
export function useLinePlayer(item: Item | null, speed: number) {
  const audio = useRef<HTMLAudioElement | null>(null);
  const [mode, setMode] = useState<"ai" | "local">("ai");
  const cancelled = useRef(false);

  function local(line: Line): Promise<void> {
    return new Promise((resolve) => {
      const u = new SpeechSynthesisUtterance(line.t);
      const acc = item!.speakers[line.s].accent;
      u.lang = acc;
      u.rate = speed;
      const voices = speechSynthesis.getVoices().filter((v) => v.lang === acc);
      const idx = Object.keys(item!.speakers).indexOf(line.s);
      if (voices.length) u.voice = voices[idx % voices.length];
      u.onend = () => resolve();
      u.onerror = () => resolve();
      speechSynthesis.speak(u);
    });
  }

  function play(i: number): Promise<void> {
    const line = item!.lines[i];
    if (mode === "local") return local(line);
    return new Promise((resolve) => {
      const sp = item!.speakers[line.s];
      const a = new Audio();
      audio.current = a;
      const fallback = () => { setMode("local"); local(line).then(resolve); };
      a.onended = () => resolve();
      a.onerror = fallback;
      playableUrl(audioUrl(line.t, sp.voice)).then((src) => { a.src = src; a.playbackRate = speed; return a.play(); }).catch(fallback);
    });
  }

  async function playFrom(start: number, end: number, onLine: (i: number) => void) {
    cancelled.current = false;
    for (let i = start; i <= end && !cancelled.current; i++) { onLine(i); await play(i); }
    onLine(-1);
  }

  function stop() { cancelled.current = true; audio.current?.pause(); stopAudio(); }
  return { play, playFrom, stop, mode };
}

export function ListeningItem() {
  const { id } = useParams();
  const [it, setIt] = useState<Item | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [speed, setSpeed] = useState(1);
  const [current, setCurrent] = useState(-1);
  const [transcript, setTranscript] = useState<"hidden" | "shown">("hidden");
  const [tab, setTab] = useState<"questions" | "dictation" | "gaps" | "expressions">("questions");
  const player = useLinePlayer(it, speed);

  useEffect(() => { api.get<Item>(`/api/listening/items/${id}`).then(setIt).catch((e) => setErr(e.message)); return () => player.stop(); }, [id]); // eslint-disable-line

  if (err) return <ErrorBox msg={err} />;
  if (!it) return <div className="text-ink-400">Loading…</div>;
  const playing = current >= 0;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <Link to="/listening" className="text-sm text-brand-500">← All recordings</Link>
      <div className="flex items-end justify-between">
        <div><div className="flex items-center gap-2"><LevelPill l={it.level} /><span className="text-xs uppercase text-ink-400">{it.kind}</span></div><div className="mt-2 flex items-center gap-3"><h1 className="h1">{it.title}</h1><BookmarkButton kind="listening" itemId={it.id} title={it.title} route={`/listening/${it.id}`} /></div>
          <p className="mt-1 text-xs text-ink-400">{Object.entries(it.speakers).map(([n, s]) => `${n} (${ACCENT_NAME[s.accent]})`).join(" · ")}</p></div>
        <span className={`pill ${player.mode === "ai" ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300" : "bg-gold-400/20 text-gold-500"}`}>
          {player.mode === "ai" ? (it.audio_cached ? "Natural voices · offline cache" : "Natural voices") : "Windows voices (no API key)"}</span>
      </div>

      <div className="card space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          {!playing ? <button className="btn-primary" onClick={() => player.playFrom(0, it.lines.length - 1, setCurrent)}>▶ Play all</button>
            : <button className="btn-primary !bg-rose-600" onClick={() => { player.stop(); setCurrent(-1); }}>■ Stop</button>}
          <div className="flex items-center gap-1 text-sm"><span className="label !mb-0 mr-1">Speed</span>{SPEEDS.map((s) => <button key={s} onClick={() => setSpeed(s)} className={`rounded-lg px-2 py-1 ${speed === s ? "bg-brand-600 text-white" : "hover:bg-ink-100 dark:hover:bg-ink-800"}`}>{s}×</button>)}</div>
          <div className="ml-auto flex items-center gap-1 text-sm"><span className="label !mb-0 mr-1">Transcript</span>
            {(["hidden", "shown"] as const).map((m) => <button key={m} onClick={() => setTranscript(m)} className={`rounded-lg px-2 py-1 capitalize ${transcript === m ? "bg-brand-600 text-white" : "hover:bg-ink-100 dark:hover:bg-ink-800"}`}>{m}</button>)}</div>
        </div>
        <p className="text-xs text-ink-400">Tip: listen once without the transcript and answer the questions, then turn it on and replay difficult lines.</p>
        <ol className="space-y-1">
          {it.lines.map((l, i) => (
            <li key={i} className={`flex items-start gap-3 rounded-xl px-3 py-2 transition ${current === i ? "bg-brand-50 dark:bg-brand-500/10" : ""}`}>
              <button title="Replay this line" onClick={() => { player.stop(); setTimeout(() => player.playFrom(i, i, setCurrent), 50); }} className="mt-0.5 shrink-0 text-brand-500 hover:text-brand-700">↻</button>
              <span className="w-24 shrink-0 text-sm font-medium text-ink-400">{l.s}</span>
              <span className={transcript === "hidden" ? "select-none blur-sm" : ""}>{l.t}</span>
            </li>
          ))}
        </ol>
      </div>

      <div className="flex gap-1">{(["questions", "dictation", "gaps", "expressions"] as const).map((t) => <button key={t} onClick={() => setTab(t)} className={tab === t ? "btn-primary" : "btn-ghost"}>{{ questions: "Questions", dictation: "Dictation", gaps: "Fill the gaps", expressions: "Expressions" }[t]}</button>)}</div>
      {tab === "questions" && <Questions it={it} />}
      {tab === "dictation" && <Dictation it={it} play={(i) => player.playFrom(i, i, setCurrent)} />}
      {tab === "gaps" && <Gaps it={it} play={(i) => player.playFrom(i, i, setCurrent)} />}
      {tab === "expressions" && (
        <div className="card"><ul className="space-y-2">{it.expressions.map((e) => <li key={e.phrase}><b>{e.phrase}</b> <span className="text-ink-400">— {e.meaning}</span></li>)}</ul></div>
      )}
    </div>
  );
}

function Questions({ it }: { it: Item }) {
  const [res, setRes] = useState<Record<string, { correct: boolean; answer: string; explanation: string; chosen: string }>>({});
  async function pick(qid: string, o: string) {
    const r = await api.post<{ correct: boolean; answer: string; explanation: string }>(`/api/listening/items/${it.id}/answer`, { question_id: qid, answer: o });
    setRes((x) => ({ ...x, [qid]: { ...r, chosen: o } }));
  }
  return (
    <div className="card space-y-5">{it.questions.map((q, n) => {
      const r = res[q.id];
      return (
        <div key={q.id}>
          <div className="mb-2 text-sm font-medium">{n + 1}. {q.prompt}</div>
          <div className="grid grid-cols-2 gap-2">{q.options.map((o) => (
            <button key={o} disabled={!!r} onClick={() => pick(q.id, o)} className={`btn-ghost !justify-start text-left ${r && o === r.answer ? "!border-emerald-500 !bg-emerald-50 dark:!bg-emerald-500/10" : r && o === r.chosen ? "!border-rose-500 !bg-rose-50 dark:!bg-rose-500/10" : ""}`}>{o}</button>
          ))}</div>
          {r && <p className="mt-2 text-sm text-ink-600 dark:text-ink-400">{r.explanation}</p>}
        </div>
      );
    })}</div>
  );
}

export function WordDiff({ words }: { words: AlignWord[] }) {
  return (
    <p className="leading-8">{words.map((w, i) => w.status === "ok" ? <span key={i}>{w.word} </span>
      : w.status === "extra" ? <span key={i} className="text-ink-400 line-through">{w.heard} </span>
      : <span key={i} title={w.heard ? `heard: ${w.heard}` : "missing"} className={`rounded px-1 ${w.status === "missed" ? "bg-gold-400/20 text-gold-500" : "bg-rose-100 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300"}`}>{w.word}{w.heard ? ` (${w.heard})` : ""} </span>)}</p>
  );
}

function Dictation({ it, play }: { it: Item; play: (i: number) => void }) {
  const [text, setText] = useState<Record<number, string>>({});
  const [res, setRes] = useState<Record<number, { score: number; words: AlignWord[] }>>({});
  async function check(line: number) {
    const r = await api.post<{ score: number; words: AlignWord[] }>(`/api/listening/items/${it.id}/dictation`, { line, text: text[line] ?? "" });
    setRes((x) => ({ ...x, [line]: r }));
  }
  return (
    <div className="card space-y-6">
      <p className="muted">Play each sentence (as many times as you need) and type exactly what you hear. Keep the transcript hidden.</p>
      {it.dictation.map((line, n) => (
        <div key={line} className="space-y-2">
          <div className="flex items-center gap-2"><button className="btn-ghost" onClick={() => play(line)}>▶ Sentence {n + 1}</button><span className="text-xs text-ink-400">{it.lines[line].s}</span></div>
          <div className="flex gap-2"><input className="input" value={text[line] ?? ""} disabled={!!res[line]} onChange={(e) => setText({ ...text, [line]: e.target.value })} />
            <button className="btn-primary" disabled={!!res[line] || !(text[line] ?? "").trim()} onClick={() => check(line)}>Check</button></div>
          {res[line] && <div className="rounded-xl bg-ink-50 p-3 text-sm dark:bg-ink-950"><b>{Math.round(res[line].score * 100)}%</b> <WordDiff words={res[line].words} /><p className="text-xs text-ink-400">Yellow = missed · red = misheard (what you wrote in brackets) · struck-through = extra words</p></div>}
        </div>
      ))}
    </div>
  );
}

function Gaps({ it, play }: { it: Item; play: (i: number) => void }) {
  const [vals, setVals] = useState<Record<number, string[]>>({});
  const [res, setRes] = useState<Record<number, boolean[]>>({});
  async function check(line: number) {
    const r = await api.post<{ results: boolean[] }>(`/api/listening/items/${it.id}/gaps`, { line, answers: vals[line] ?? [] });
    setRes((x) => ({ ...x, [line]: r.results }));
  }
  return (
    <div className="card space-y-6">
      {it.gaps.map((g) => {
        let text = it.lines[g.line].t;
        g.words.forEach((w, k) => { text = text.replace(w, `§${k}§`); });
        const parts = text.split(/§(\d+)§/);
        return (
          <div key={g.line} className="space-y-2">
            <button className="btn-ghost" onClick={() => play(g.line)}>▶ Play</button>
            <p className="leading-10">{parts.map((p, k) => k % 2 === 0 ? <span key={k}>{p}</span> : (
              <input key={k} className={`input !inline-block !w-44 !py-1 ${res[g.line] ? (res[g.line][+p] ? "!border-emerald-500" : "!border-rose-500") : ""}`}
                value={(vals[g.line] ?? [])[+p] ?? ""} disabled={!!res[g.line]}
                onChange={(e) => { const a = [...(vals[g.line] ?? [])]; a[+p] = e.target.value; setVals({ ...vals, [g.line]: a }); }} />
            ))}</p>
            {res[g.line] ? <p className="text-sm text-ink-400">Answer: {g.words.join(" · ")}</p> : <button className="btn-primary" onClick={() => check(g.line)}>Check</button>}
          </div>
        );
      })}
    </div>
  );
}
