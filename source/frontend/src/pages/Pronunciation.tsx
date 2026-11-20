import { useEffect, useRef, useState } from "react";
import { api, ApiError, SpeechMetrics } from "../lib/api";
import { Recorder, speakLocal } from "../lib/speech";
import { useProfile } from "../App";
import { ErrorBox, LevelPill, Speak } from "../components/ui";
import { WordDiff } from "./Listening";
import { toWav16k } from "../lib/wav";

interface Sound { ipa: string; type: string; name: string; examples: string[]; tip: string; french_trap: boolean }
interface PairSet { id: string; contrast: string; pairs: [string, string][] }
interface Content { sounds: Sound[]; minimal_pairs: PairSet[]; word_stress: { word: string; stress: string }[]; shadowing: { id: string; level: string; focus: string; text: string }[] }
interface Assessment {
  pronunciation_score: number | null; accuracy: number | null; fluency: number | null; completeness: number | null; prosody: number | null;
  recognised: string; words: { word: string; accuracy: number | null; error_type: string; phonemes: { phoneme: string; accuracy: number | null }[] }[];
}
interface CheckResult { score: number; words: { word: string | null; status: "ok" | "wrong" | "missed" | "extra"; heard?: string | null }[]; heard: string; metrics: SpeechMetrics; note: string }

type Tab = "sounds" | "pairs" | "stress" | "shadow";

export default function Pronunciation() {
  const [c, setC] = useState<Content | null>(null);
  const [tab, setTab] = useState<Tab>("shadow");
  useEffect(() => { api.get<Content>("/api/pronunciation/content").then(setC); }, []);
  if (!c) return <div className="text-ink-400">Loading…</div>;
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div><h1 className="h1">Pronunciation Lab</h1><p className="muted mt-1">Sounds, minimal pairs, word stress, and shadowing with record-and-compare. Focused on the sounds French speakers find hardest.</p></div>
      <div className="flex gap-1">{([["shadow", "Shadowing & read-aloud"], ["sounds", "Sounds (IPA)"], ["pairs", "Minimal pairs"], ["stress", "Word stress"]] as [Tab, string][]).map(([k, l]) => <button key={k} onClick={() => setTab(k)} className={tab === k ? "btn-primary" : "btn-ghost"}>{l}</button>)}</div>
      {tab === "sounds" && <Sounds sounds={c.sounds} />}
      {tab === "pairs" && <Pairs sets={c.minimal_pairs} />}
      {tab === "stress" && <Stress items={c.word_stress} />}
      {tab === "shadow" && <Shadowing items={c.shadowing} />}
    </div>
  );
}

function Sounds({ sounds }: { sounds: Sound[] }) {
  const { profile } = useProfile();
  const [onlyTraps, setOnlyTraps] = useState(true);
  return (
    <div className="space-y-3">
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={onlyTraps} onChange={(e) => setOnlyTraps(e.target.checked)} /> Show only sounds French speakers typically find difficult</label>
      <div className="grid grid-cols-2 gap-4">{sounds.filter((s) => !onlyTraps || s.french_trap).map((s) => (
        <div key={s.ipa} className="card !p-5">
          <div className="flex items-baseline justify-between"><span className="font-serif text-3xl">/{s.ipa}/</span><span className="text-xs uppercase text-ink-400">{s.type} · {s.name}</span></div>
          <p className="mt-2 text-sm">{s.tip}</p>
          <div className="mt-3 flex flex-wrap gap-2">{s.examples.map((e) => <span key={e} className="flex items-center rounded-lg bg-ink-50 pl-2 text-sm dark:bg-ink-950">{e}<Speak text={e} accent={profile.accent_preference} /></span>)}</div>
        </div>
      ))}</div>
    </div>
  );
}

function Pairs({ sets }: { sets: PairSet[] }) {
  const { profile } = useProfile();
  const [set, setSet] = useState(sets[0]);
  const [round, setRound] = useState(0);
  const [target, setTarget] = useState<{ pair: [string, string]; word: string } | null>(null);
  const [score, setScore] = useState(0);
  const [last, setLast] = useState<{ ok: boolean; word: string } | null>(null);
  const ROUNDS = 10;

  function next() {
    const pair = set.pairs[Math.floor(Math.random() * set.pairs.length)];
    const word = pair[Math.floor(Math.random() * 2)];
    setTarget({ pair, word }); setLast(null);
    speakLocal(word, profile.accent_preference, 0.9);
  }
  function start(s: PairSet) { setSet(s); setRound(0); setScore(0); setTarget(null); setLast(null); }
  async function choose(w: string) {
    if (!target || last) return;
    const ok = w === target.word;
    const newScore = score + (ok ? 1 : 0);
    setScore(newScore); setLast({ ok, word: target.word });
    const r = round + 1; setRound(r);
    if (r === ROUNDS) await api.post("/api/pronunciation/minimal-pairs/result", { set_id: set.id, correct: newScore, total: ROUNDS });
  }

  return (
    <div className="grid grid-cols-[260px_1fr] gap-6">
      <div className="card space-y-1 !p-3">{sets.map((s) => <button key={s.id} onClick={() => start(s)} className={`w-full rounded-lg px-3 py-2 text-left text-sm ${s.id === set.id ? "bg-brand-50 font-medium text-brand-700 dark:bg-brand-500/15 dark:text-brand-100" : "hover:bg-ink-50 dark:hover:bg-ink-800"}`}>/{s.contrast.replace(" vs ", "/ vs /")}/</button>)}</div>
      <div className="card space-y-5 text-center">
        <div className="text-sm text-ink-400">Round {Math.min(round + (last ? 0 : 1), ROUNDS)} of {ROUNDS} · Score {score}</div>
        {round >= ROUNDS ? (
          <div><p className="font-serif text-3xl">{score}/{ROUNDS}</p><p className="muted mt-2">{score >= 9 ? "Excellent ear." : score >= 7 ? "Good — keep practising the ones you missed." : "This contrast needs work. Listen to each pair slowly below."}</p><button className="btn-primary mt-4" onClick={() => start(set)}>Try again</button></div>
        ) : !target || last ? (
          <div className="space-y-3">
            {last && <p className={last.ok ? "text-emerald-500" : "text-rose-500"}>{last.ok ? "✓ Correct" : `✗ It was “${last.word}”`}</p>}
            <button className="btn-primary" onClick={next}>{target ? "Next word" : "Start: listen and choose"}</button>
          </div>
        ) : (
          <div className="space-y-4">
            <button className="btn-ghost" onClick={() => speakLocal(target.word, profile.accent_preference, 0.9)}>🔊 Play again</button>
            <div className="flex justify-center gap-4">{target.pair.map((w) => <button key={w} onClick={() => choose(w)} className="btn-ghost !px-8 !py-4 font-serif text-2xl">{w}</button>)}</div>
          </div>
        )}
        <div className="border-t border-ink-100 pt-4 text-left dark:border-ink-800">
          <div className="label">All pairs: listen, then say both aloud</div>
          <div className="grid grid-cols-2 gap-2 text-sm">{set.pairs.map(([a, b]) => <div key={a} className="flex items-center gap-1">{a}<Speak text={a} accent={profile.accent_preference} /> / {b}<Speak text={b} accent={profile.accent_preference} /></div>)}</div>
        </div>
      </div>
    </div>
  );
}

function Stress({ items }: { items: { word: string; stress: string }[] }) {
  const { profile } = useProfile();
  return (
    <div className="card">
      <p className="muted mb-4">The CAPITAL syllable is stressed: louder, longer, higher. Unstressed syllables often become the weak /ə/. Word families shift stress — a common source of misunderstanding.</p>
      <div className="grid grid-cols-2 gap-x-8 gap-y-2">{items.map((w) => (
        <div key={w.word} className="flex items-center justify-between border-b border-ink-100 py-1 dark:border-ink-800"><span>{w.word}</span><span className="flex items-center font-mono text-sm">{w.stress}<Speak text={w.word.replace(/ \(.*\)/, "")} accent={profile.accent_preference} /></span></div>
      ))}</div>
    </div>
  );
}

function Shadowing({ items }: { items: { id: string; level: string; focus: string; text: string }[] }) {
  const { profile } = useProfile();
  const [sel, setSel] = useState(items[0]);
  const [custom, setCustom] = useState("");
  const [rate, setRate] = useState(0.9);
  const [recording, setRecording] = useState(false);
  const [mine, setMine] = useState<{ url: string; blob: Blob } | null>(null);
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<CheckResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [azureOn, setAzureOn] = useState(false);
  const [deep, setDeep] = useState<Assessment | null>(null);
  useEffect(() => { api.get<{ keys: Record<string, boolean>; azure_speech_region: string }>("/api/system/providers").then((p) => setAzureOn(p.keys.azure_speech && !!p.azure_speech_region)).catch(() => {}); }, []);
  const rec = useRef(new Recorder());
  const target = custom.trim() || sel.text;

  function choose(s: typeof sel) { setSel(s); setCustom(""); setMine(null); setRes(null); setDeep(null); setErr(null); }

  async function toggle() {
    setErr(null);
    if (!recording) {
      try { await rec.current.start(profile.accent_preference); setRecording(true); setRes(null); } catch { setErr("Microphone not available. Check Windows Settings › Privacy › Microphone."); }
      return;
    }
    setRecording(false);
    const blob = await rec.current.stop();
    if (mine) URL.revokeObjectURL(mine.url);
    setMine({ url: URL.createObjectURL(blob), blob });
  }

  async function check() {
    if (!mine) return;
    setBusy(true); setErr(null);
    const fd = new FormData();
    fd.append("audio", mine.blob, "speech.webm"); fd.append("target", target); fd.append("item_id", custom.trim() ? "custom" : sel.id);
    rec.current.attach(fd);
    try { setRes(await api.upload<CheckResult>("/api/pronunciation/read-aloud", fd)); }
    catch (e) { setErr((e as ApiError).status === 412 ? "No speech was recognised. Record again a little closer to the microphone (Chrome's free recognition), or add an OpenAI key for Whisper." : (e as Error).message); }
    finally { setBusy(false); }
  }

  async function assess() {
    if (!mine) return;
    setBusy(true); setErr(null);
    try {
      const fd = new FormData();
      fd.append("audio", await toWav16k(mine.blob), "speech.wav"); fd.append("target", target); fd.append("item_id", custom.trim() ? "custom" : sel.id);
      setDeep(await api.upload<Assessment>("/api/pronunciation/assess", fd));
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }

  return (
    <div className="grid grid-cols-[300px_1fr] gap-6">
      <div className="card space-y-1 !p-3">{items.map((s) => (
        <button key={s.id} onClick={() => choose(s)} className={`w-full rounded-lg px-3 py-2 text-left text-sm ${s.id === sel.id && !custom ? "bg-brand-50 dark:bg-brand-500/15" : "hover:bg-ink-50 dark:hover:bg-ink-800"}`}>
          <div className="flex items-center justify-between"><span className="font-medium">{s.focus}</span><LevelPill l={s.level} /></div>
        </button>
      ))}</div>
      <div className="card space-y-5">
        <p className="font-serif text-2xl leading-relaxed">{target}</p>
        <input className="input" placeholder="…or paste any sentence you want to practise" value={custom} onChange={(e) => { setCustom(e.target.value); setMine(null); setRes(null); }} />
        <ol className="space-y-4 text-sm">
          <li className="flex items-center gap-3"><span className="w-5 text-ink-400">1</span><button className="btn-ghost" onClick={() => speakLocal(target, profile.accent_preference, rate)}>🔊 Listen to the model</button>
            <span className="flex items-center gap-1 text-xs text-ink-400">speed {[0.7, 0.9, 1].map((r) => <button key={r} onClick={() => setRate(r)} className={`rounded px-1.5 ${rate === r ? "bg-brand-600 text-white" : ""}`}>{r}×</button>)}</span></li>
          <li className="flex items-center gap-3"><span className="w-5 text-ink-400">2</span><button className={recording ? "btn-primary animate-pulse !bg-rose-600" : "btn-primary"} onClick={toggle}>{recording ? "■ Stop recording" : "● Record yourself"}</button><span className="text-xs text-ink-400">Shadow the model: same rhythm, same stress, same melody.</span></li>
          <li className="flex items-center gap-3"><span className="w-5 text-ink-400">3</span>
            {mine ? <><audio src={mine.url} controls className="h-9" /><button className="btn-ghost" onClick={() => speakLocal(target, profile.accent_preference, rate)}>Model again</button></> : <span className="text-ink-400">Compare your recording with the model.</span>}</li>
          <li className="flex items-center gap-3"><span className="w-5 text-ink-400">4</span><button className="btn-ghost" disabled={!mine || busy} onClick={check}>{busy ? "Checking…" : "Check clarity with AI"}</button>
            {azureOn ? <button className="btn-ghost" disabled={!mine || busy} onClick={assess}>Phoneme-level scoring (Azure)</button>
              : <span className="text-xs text-ink-400">Add an Azure Speech key in Settings for sound-by-sound scoring.</span>}</li>
        </ol>
        <ErrorBox msg={err} />
        {deep && <PhonemeReport a={deep} />}
        {res && (
          <div className="space-y-2 rounded-xl bg-ink-50 p-4 text-sm dark:bg-ink-950">
            <div className="flex items-center justify-between"><span className="font-serif text-2xl">{Math.round(res.score * 100)}% clear</span>
              <span className="text-xs text-ink-400">{res.metrics.words_per_minute ?? "–"} wpm · {res.metrics.long_pauses} long pauses · {res.metrics.filler_words} fillers</span></div>
            <WordDiff words={res.words} />
            <p className="text-xs text-ink-400">Recogniser heard: “{res.heard}”</p>
            <p className="text-xs text-ink-400">{res.note}</p>
          </div>
        )}
      </div>
    </div>
  );
}

const tone = (v: number | null) => v == null ? "text-ink-400" : v >= 80 ? "text-emerald-600 dark:text-emerald-400" : v >= 60 ? "text-gold-500" : "text-rose-600 dark:text-rose-400";

function PhonemeReport({ a }: { a: Assessment }) {
  return (
    <div className="space-y-3 rounded-xl bg-ink-50 p-4 text-sm dark:bg-ink-950">
      <div className="flex flex-wrap gap-4">
        {([["Overall", a.pronunciation_score], ["Accuracy", a.accuracy], ["Fluency", a.fluency], ["Completeness", a.completeness], ["Prosody", a.prosody]] as [string, number | null][])
          .filter(([, v]) => v != null).map(([k, v]) => <div key={k}><div className="label">{k}</div><div className={`font-serif text-2xl ${tone(v)}`}>{Math.round(v!)}</div></div>)}
      </div>
      <div className="flex flex-wrap gap-3">{a.words.map((w, i) => (
        <div key={i} className="rounded-lg border border-ink-200 px-2 py-1 dark:border-ink-800">
          <div className={`font-medium ${tone(w.accuracy)}`}>{w.word} <span className="text-xs">{w.accuracy != null ? Math.round(w.accuracy) : ""}</span></div>
          {w.error_type !== "None" && <div className="text-[10px] uppercase text-rose-500">{w.error_type}</div>}
          <div className="flex gap-1 font-mono text-xs">{w.phonemes.map((p, k) => <span key={k} className={tone(p.accuracy)} title={`${p.accuracy ?? "–"}/100`}>{p.phoneme}</span>)}</div>
        </div>
      ))}</div>
      <p className="text-xs text-ink-400">Scores from Azure AI Speech Pronunciation Assessment (0–100). Red sounds are below 60: practise them with Minimal pairs.</p>
    </div>
  );
}
