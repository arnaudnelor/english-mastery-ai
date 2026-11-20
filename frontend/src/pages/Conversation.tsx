import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { HandsFree } from "../lib/vad";
import { BrowserListener, browserSttAvailable } from "../lib/browserStt";
import { api, ApiError, Feedback, SpeechMetrics, TurnResult } from "../lib/api";
import { Recorder, speakAI, speakLocal, stopAudio } from "../lib/speech";
import { useProfile } from "../App";
import { CategoryPill, ErrorBox, Speak } from "../components/ui";

interface Mode { id: string; title: string; brief: string }
interface Msg { role: "user" | "assistant"; text: string; feedback?: Feedback | null; metrics?: SpeechMetrics | null; deferred?: boolean }
interface Summary {
  strengths: string[]; recurring_issues: string[]; vocabulary_to_learn: { word: string; meaning: string }[];
  estimated_cefr: string; practice_band_estimate: number | null; next_steps: string[]; disclaimer?: string;
}

const CORRECTION_LABEL: Record<string, string> = {
  immediate: "Immediate (teacher recasts in-line)",
  after_response: "After each response",
  end_of_conversation: "End-of-conversation feedback",
  strict: "Strict examination mode",
};

export default function Conversation() {
  const { profile } = useProfile();
  const [modes, setModes] = useState<Mode[]>([]);
  const [params] = useSearchParams();
  const [mode, setMode] = useState(params.get("mode") ?? "free");
  const [persona, setPersona] = useState("professor");
  const [correction, setCorrection] = useState(profile.correction_mode);
  const [cid, setCid] = useState<number | null>(null);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [recording, setRecording] = useState(false);
  const [autoSpeak, setAutoSpeak] = useState(true);
  const [err, setErr] = useState<{ msg: string; key?: boolean } | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const rec = useRef(new Recorder());
  const hf = useRef<HandsFree | null>(null);
  const bl = useRef<BrowserListener | null>(null);
  const [whisper, setWhisper] = useState(false); // OpenAI key configured -> Whisper with pause analysis
  const [interim, setInterim] = useState("");
  const [aiSpeaking, setAiSpeaking] = useState(false);
  const [handsFree, setHandsFree] = useState(false);
  const [level, setLevel] = useState<{ v: number; speaking: boolean }>({ v: 0, speaking: false });
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.get<{ modes: Mode[] }>("/api/conversation/modes").then((r) => setModes(r.modes));
    api.get<{ keys: Record<string, boolean> }>("/api/system/providers").then((p) => setWhisper(!!p.keys.openai)).catch(() => {});
    return () => { stopAudio(); hf.current?.stop(); bl.current?.stop(); };
  }, []);
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, busy]);

  const fail = (e: unknown) => {
    const a = e as ApiError;
    setErr({ msg: a.message, key: a.status === 412 });
  };

  async function start() {
    setErr(null); setSummary(null);
    try {
      const r = await api.post<{ conversation_id: number; opener: string }>("/api/conversation/start", { mode, correction_mode: correction });
      setCid(r.conversation_id);
      setMsgs([{ role: "assistant", text: r.opener }]);
      if (autoSpeak) speakAI(r.opener, profile.accent_preference);
    } catch (e) { fail(e); }
  }

  function handle(r: TurnResult) {
    setMsgs((m) => [...m, { role: "user", text: r.transcript, feedback: r.feedback, metrics: r.speech_metrics, deferred: r.feedback_deferred }, { role: "assistant", text: r.reply }]);
    if (autoSpeak) {
      setAiSpeaking(true);
      if (bl.current) bl.current.paused = true; // don't let the microphone hear the professor
      speakAI(r.reply, profile.accent_preference, () => { setAiSpeaking(false); if (bl.current) bl.current.paused = false; });
    } else if (bl.current) bl.current.paused = false;
  }

  async function sendText(e?: React.FormEvent) {
    e?.preventDefault();
    if (!cid || !text.trim()) return;
    setBusy(true); setErr(null);
    try { handle(await api.post<TurnResult>(`/api/conversation/${cid}/turn`, { text, persona })); setText(""); }
    catch (x) { fail(x); } finally { setBusy(false); }
  }

  async function sendSpokenText(text: string, durationSec: number) {
    setBusy(true); setErr(null); setInterim("");
    if (bl.current) bl.current.paused = true;
    try { handle(await api.post<TurnResult>(`/api/conversation/${cid}/turn`, { text, persona, speech: { duration_sec: durationSec, source: "browser" } })); }
    catch (x) { fail(x); if (bl.current) bl.current.paused = false; }
    finally { setBusy(false); }
  }

  async function sendVoice(blob: Blob, transcript = "", duration = 0) {
    setBusy(true);
    if (hf.current) hf.current.paused = true; // don't capture while the professor is thinking
    try {
      const fd = new FormData();
      fd.append("audio", blob, "speech.webm");
      fd.append("persona", persona);
      if (transcript) { fd.append("transcript", transcript); fd.append("duration", String(duration)); }
      handle(await api.upload<TurnResult>(`/api/conversation/${cid}/voice-turn`, fd));
    } catch (x) {
      if ((x as ApiError).status !== 422) fail(x); // 422 = no speech heard: just keep listening
    } finally {
      setBusy(false);
      if (hf.current) hf.current.paused = false; // listening again (you can interrupt the reply)
    }
  }

  async function toggleMic() {
    if (!cid) return;
    setErr(null);
    if (!recording) {
      try { stopAudio(); await rec.current.start(profile.accent_preference); setRecording(true); }
      catch { setErr({ msg: "Microphone not available. Check Windows Settings › Privacy › Microphone." }); }
      return;
    }
    setRecording(false);
    const blob = await rec.current.stop();
    if (!whisper && !rec.current.transcript) { setErr({ msg: "I couldn't hear any speech. Speak a little louder or closer to the microphone, then try again." }); return; }
    await sendVoice(blob, rec.current.transcript, rec.current.duration);
  }

  async function toggleHandsFree() {
    setErr(null);
    if (hf.current || bl.current) { hf.current?.stop(); hf.current = null; bl.current?.stop(); bl.current = null; setHandsFree(false); return; }
    if (!whisper && browserSttAvailable()) {
      // Free mode: Chrome's own speech recognition sends each sentence when you pause
      const l = new BrowserListener({ lang: profile.accent_preference, onSentence: (t, d) => sendSpokenText(t, d), onInterim: setInterim });
      if (l.start()) { bl.current = l; setHandsFree(true); } else setErr({ msg: "Speech recognition could not start. Allow the microphone for this site in Chrome." });
      return;
    }
    const h = new HandsFree({
      onUtterance: (b) => sendVoice(b),
      onSpeechStart: () => stopAudio(), // barge-in: stop the AI voice when you start talking
      onLevel: (v, speaking) => setLevel({ v, speaking }),
    });
    try { await h.start(); hf.current = h; setHandsFree(true); }
    catch { setErr({ msg: "Microphone not available. Check Windows Settings › Privacy › Microphone." }); }
  }

  async function end() {
    if (!cid) return;
    setBusy(true);
    try { setSummary(await api.post<Summary>(`/api/conversation/${cid}/end`)); } catch (x) { fail(x); } finally { setBusy(false); }
  }

  // ---------- setup screen ----------
  if (!cid) {
    return (
      <div className="mx-auto max-w-5xl space-y-6">
        <div><h1 className="h1">AI Conversation Lab</h1><p className="muted mt-1">Speak with your AI professor. Every sentence you say is transcribed, analysed and tracked.</p></div>
        <div className="grid grid-cols-3 gap-3">
          {modes.map((m) => (
            <button key={m.id} onClick={() => setMode(m.id)}
              className={`card !p-4 text-left transition ${mode === m.id ? "!border-brand-500 ring-2 ring-brand-100 dark:ring-brand-700/40" : "hover:border-ink-400"}`}>
              <div className="font-medium">{m.title}</div><div className="mt-1 text-xs text-ink-400">{m.brief}</div>
            </button>
          ))}
        </div>
        <div className="card grid grid-cols-3 gap-4">
          <div><label className="label">Teacher personality</label>
            <select className="input" value={persona} onChange={(e) => setPersona(e.target.value)}>
              <option value="professor">Warm professor</option><option value="coach">Energetic coach</option><option value="executive">Direct executive</option><option value="examiner">Neutral examiner</option></select></div>
          <div><label className="label">Corrections</label>
            <select className="input" value={correction} onChange={(e) => setCorrection(e.target.value)}>
              {Object.entries(CORRECTION_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></div>
          <div><label className="label">Voice</label>
            <label className="flex h-10 items-center gap-2 text-sm"><input type="checkbox" checked={autoSpeak} onChange={(e) => setAutoSpeak(e.target.checked)} /> Read replies aloud</label></div>
          <div className="col-span-3 flex items-center justify-between">
            <p className="text-xs text-ink-400">Accent: {profile.accent_preference} (change in Settings). Requires an API key and internet.</p>
            <button className="btn-primary" onClick={start}>Start conversation</button>
          </div>
        </div>
        <KeyError err={err} />
      </div>
    );
  }

  // ---------- live conversation ----------
  return (
    <div className="mx-auto flex h-full max-w-4xl flex-col">
      <div className="mb-4 flex items-center justify-between">
        <div><h1 className="font-serif text-2xl">{modes.find((m) => m.id === mode)?.title}</h1><p className="text-xs text-ink-400">{CORRECTION_LABEL[correction]}</p></div>
        <div className="flex gap-2">
          <button className="btn-ghost" onClick={end} disabled={busy || msgs.length < 2}>End & get feedback</button>
          <button className="btn-ghost" onClick={() => { stopAudio(); hf.current?.stop(); hf.current = null; bl.current?.stop(); bl.current = null; setHandsFree(false); setCid(null); setMsgs([]); setSummary(null); }}>New</button>
        </div>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto pb-4">
        {msgs.map((m, i) => (
          <div key={i} className={m.role === "user" ? "ml-16" : "mr-16"}>
            <div className={`rounded-2xl px-4 py-3 ${m.role === "user" ? "bg-brand-600 text-white" : "bg-white shadow-sm dark:bg-ink-900"}`}>
              <div className="flex items-start justify-between gap-3"><span>{m.text}</span>
                {m.role === "assistant" && <button className="text-xs text-brand-500 hover:underline" onClick={() => speakAI(m.text, profile.accent_preference)}>replay</button>}</div>
            </div>
            {m.metrics && <MetricsLine m={m.metrics} />}
            {m.feedback && <FeedbackCard f={m.feedback} accent={profile.accent_preference} />}
            {m.deferred && <p className="mt-1 text-right text-xs text-ink-400">Feedback saved for the end of the conversation.</p>}
          </div>
        ))}
        {busy && <div className="mr-16 text-sm text-ink-400">Your professor is listening and thinking…</div>}
        {summary && <SummaryCard s={summary} />}
        <div ref={bottom} />
      </div>

      <KeyError err={err} />
      <div className="mt-2 flex items-center justify-between rounded-xl bg-white px-4 py-2 text-sm shadow-sm dark:bg-ink-900">
        <button type="button" onClick={toggleHandsFree} className={handsFree ? "btn-primary !bg-emerald-600" : "btn-ghost"}>
          {handsFree ? "● Hands-free ON: just talk" : "Turn on hands-free conversation"}</button>
        {handsFree && (
          <div className="flex items-center gap-3 text-xs text-ink-400">
            <span>{busy ? "Thinking…" : bl.current ? (aiSpeaking ? "The professor is speaking…" : interim ? `“${interim}”` : "Listening… just talk, then pause") : level.speaking ? "Listening to you…" : "Waiting for you to speak (you can interrupt the professor)"}</span>
            {aiSpeaking && <button type="button" className="btn-ghost !py-0.5 text-xs" onClick={() => { stopAudio(); setAiSpeaking(false); if (bl.current) bl.current.paused = false; }}>Interrupt</button>}
            {!bl.current && <div className="h-2 w-28 rounded-full bg-ink-100 dark:bg-ink-800"><div className={`h-2 rounded-full ${level.speaking ? "bg-emerald-500" : "bg-ink-400"}`} style={{ width: `${Math.round(level.v * 100)}%` }} /></div>}
          </div>
        )}
      </div>
      <form onSubmit={sendText} className="mt-2 flex items-center gap-3">
        <button type="button" onClick={toggleMic} disabled={busy || handsFree}
          className={`grid h-14 w-14 shrink-0 place-items-center rounded-full text-white shadow-lg transition ${recording ? "animate-pulse bg-rose-600" : "bg-brand-600 hover:bg-brand-700"} disabled:opacity-50`}
          title={recording ? "Stop and send" : "Start speaking"}>
          {recording ? <span className="h-4 w-4 rounded-sm bg-white" /> :
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="2" width="6" height="12" rx="3" /><path d="M5 10a7 7 0 0 0 14 0M12 19v3" /></svg>}
        </button>
        <input className="input !py-3" placeholder={recording ? "Recording… click the button again to send" : "Or type your answer…"} value={text} onChange={(e) => setText(e.target.value)} disabled={busy || recording} />
        <button className="btn-primary !py-3" disabled={busy || recording || !text.trim()}>Send</button>
      </form>
    </div>
  );
}

function KeyError({ err }: { err: { msg: string; key?: boolean } | null }) {
  if (!err) return null;
  return <ErrorBox msg={err.msg} action={err.key ? <Link to="/settings" className="font-medium underline">Open Settings</Link> : undefined} />;
}

function MetricsLine({ m }: { m: SpeechMetrics }) {
  return (
    <div className="mt-1 flex justify-end gap-3 text-xs text-ink-400">
      {m.words_per_minute != null && <span>{m.words_per_minute} wpm</span>}
      <span>{m.long_pauses} long pause{m.long_pauses === 1 ? "" : "s"}</span>
      <span>{m.filler_words} filler{m.filler_words === 1 ? "" : "s"}</span>
    </div>
  );
}

function FeedbackCard({ f, accent }: { f: Feedback; accent: string }) {
  if (f.is_correct && !f.advanced_alternative) {
    return <div className="mt-2 rounded-xl bg-emerald-50 px-4 py-2 text-sm text-emerald-800 dark:bg-emerald-500/10 dark:text-emerald-300">✓ Accurate and natural.</div>;
  }
  return (
    <div className="mt-2 space-y-3 rounded-2xl border border-ink-200 bg-white p-4 text-sm dark:border-ink-800 dark:bg-ink-900">
      {!f.is_correct && (
        <div><div className="label">Corrected</div>
          <div className="flex items-center gap-2 font-medium">{f.corrected_sentence}<Speak text={f.corrected_sentence} accent={accent} /></div></div>
      )}
      {f.issues.map((i, k) => (
        <div key={k} className="border-l-2 border-ink-200 pl-3 dark:border-ink-800">
          <div className="flex items-center gap-2"><CategoryPill c={i.category} /><span className="text-rose-500 line-through">{i.original}</span>→<span className="text-emerald-600 dark:text-emerald-400">{i.corrected}</span></div>
          <p className="mt-1 text-ink-600 dark:text-ink-400">{i.explanation}</p>
          {i.explanation_fr && <p className="mt-1 italic text-ink-400">🇫🇷 {i.explanation_fr}</p>}
        </div>
      ))}
      {f.advanced_alternative && (
        <div><div className="label">More advanced</div><div className="flex items-center gap-2">{f.advanced_alternative}<Speak text={f.advanced_alternative} accent={accent} /></div></div>
      )}
      {f.fluency_note && <p className="text-ink-600 dark:text-ink-400"><span className="label inline">Fluency · </span>{f.fluency_note}</p>}
      {f.repeat_prompt && !f.is_correct && (
        <div className="flex items-center justify-between rounded-xl bg-brand-50 px-3 py-2 text-brand-700 dark:bg-brand-500/10 dark:text-brand-100">
          <span>{f.repeat_prompt}</span>
          <button type="button" className="text-xs underline" onClick={() => speakLocal(f.corrected_sentence, accent, 0.85)}>hear it slowly</button>
        </div>
      )}
    </div>
  );
}

function SummaryCard({ s }: { s: Summary }) {
  return (
    <div className="card space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-serif text-xl">Session feedback</h2>
        <div className="text-right"><div className="font-serif text-2xl">{s.estimated_cefr}</div>
          {s.practice_band_estimate != null && <div className="text-xs text-ink-400">Practice band ≈ {s.practice_band_estimate}</div>}</div>
      </div>
      {s.disclaimer && <p className="text-xs text-gold-500">{s.disclaimer}</p>}
      <Section title="Strengths" items={s.strengths} />
      <Section title="Recurring issues" items={s.recurring_issues} />
      {s.vocabulary_to_learn?.length > 0 && <div><div className="label">Vocabulary to learn</div><ul className="space-y-1 text-sm">{s.vocabulary_to_learn.map((v) => <li key={v.word}><b>{v.word}</b> — {v.meaning}</li>)}</ul></div>}
      <Section title="Next steps" items={s.next_steps} />
    </div>
  );
}

const Section = ({ title, items }: { title: string; items: string[] }) =>
  items?.length ? <div><div className="label">{title}</div><ul className="list-disc space-y-1 pl-5 text-sm">{items.map((x) => <li key={x}>{x}</li>)}</ul></div> : null;
