import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../lib/api";
import { useProfile } from "../App";
import { ErrorBox, LevelPill, Speak } from "../components/ui";
import { ACCENT_NAME, Item, useLinePlayer } from "./Listening";
import { BookmarkButton } from "../components/Bookmark";
import { PREVIEW, SANDBOXED, playableUrl, previewVideoUrls } from "../lib/preview";

interface VideoSummary { id: number; title: string; level: string; source: "file" | "youtube"; youtube_id: string | null; has_subtitles: boolean; timed: boolean; has_study: boolean }
interface Cue { start: number | null; end: number | null; text: string }
interface Study {
  summary: string; vocabulary: { word: string; meaning: string; example: string; french: string | null }[];
  idioms: { phrase: string; meaning: string }[]; grammar: { point: string; example_from_video: string; explanation: string }[];
  questions: { prompt: string; options: string[]; answer: string; explanation: string }[];
  pronunciation_focus: { phrase: string; tip: string }[]; summary_task: string;
}
interface VideoFull extends VideoSummary { cues: Cue[]; study: Study | null }

// ---------------------------------------------------------------- hub
export function VideoHub() {
  const [tab, setTab] = useState<"scenes" | "library">("scenes");
  const [scenes, setScenes] = useState<{ id: string; title: string; level: string; kind: string; accents: string[] }[]>([]);
  const [lib, setLib] = useState<VideoSummary[]>([]);
  const load = () => api.get<VideoSummary[]>("/api/video/items").then(setLib);
  useEffect(() => { api.get<typeof scenes>("/api/listening/items").then(setScenes); load(); }, []);
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div><h1 className="h1">Video Academy</h1><p className="muted mt-1">Watch with synced subtitles, replay any sentence, and turn any video into a lesson with vocabulary, idioms, grammar and questions.</p></div>
      <div className="flex gap-1"><button className={tab === "scenes" ? "btn-primary" : "btn-ghost"} onClick={() => setTab("scenes")}>Animated scenes</button><button className={tab === "library" ? "btn-primary" : "btn-ghost"} onClick={() => setTab("library")}>My video library ({lib.length})</button></div>
      {tab === "scenes" && (
        <div className="grid grid-cols-3 gap-4">{scenes.map((s) => (
          <Link key={s.id} to={`/video/scene/${s.id}`} className="card !p-0 overflow-hidden transition hover:border-brand-400">
            <div className="grid h-28 place-items-center bg-gradient-to-br from-brand-700 to-ink-900 text-4xl">🎬</div>
            <div className="p-4"><div className="flex items-center justify-between"><span className="text-xs uppercase text-ink-400">{s.kind}</span><LevelPill l={s.level} /></div><div className="mt-1 font-medium">{s.title}</div>
              <div className="text-xs text-ink-400">{s.accents.map((a) => ACCENT_NAME[a]).join(" · ")}</div></div>
          </Link>
        ))}</div>
      )}
      {tab === "library" && <Library items={lib} reload={load} />}
    </div>
  );
}

function Library({ items, reload }: { items: VideoSummary[]; reload: () => void }) {
  const nav = useNavigate();
  const [kind, setKind] = useState<"youtube" | "file">("youtube");
  const [title, setTitle] = useState("");
  const [level, setLevel] = useState("C1");
  const [url, setUrl] = useState("");
  const [video, setVideo] = useState<File | null>(null);
  const [subs, setSubs] = useState<File | null>(null);
  const [transcript, setTranscript] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function add(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setErr(null);
    const fd = new FormData();
    fd.append("title", title); fd.append("level", level); fd.append("transcript", transcript);
    if (kind === "youtube") fd.append("youtube_url", url); else if (video) fd.append("video", video);
    if (subs) fd.append("subtitles_file", subs);
    try {
      const r = await api.upload<VideoSummary>("/api/video/items", fd);
      if (PREVIEW && kind === "file" && video) previewVideoUrls[r.id] = URL.createObjectURL(video);
      reload(); nav(`/video/${r.id}`);
    }
    catch (x) { setErr((x as Error).message); } finally { setBusy(false); }
  }

  return (
    <div className="grid grid-cols-[1fr_380px] gap-6">
      <div className="space-y-3">
        {items.length === 0 && <div className="card muted">Your library is empty. Add a video you own, or a YouTube link, on the right.</div>}
        {items.map((v) => (
          <Link key={v.id} to={`/video/${v.id}`} className="card flex items-center gap-4 !p-3 transition hover:border-brand-400">
            {v.youtube_id ? <img src={`https://i.ytimg.com/vi/${v.youtube_id}/mqdefault.jpg`} className="h-16 w-28 rounded-lg object-cover" alt="" /> : <div className="grid h-16 w-28 place-items-center rounded-lg bg-ink-100 text-2xl dark:bg-ink-800">🎞</div>}
            <div className="flex-1"><div className="font-medium">{v.title}</div><div className="text-xs text-ink-400">{v.source === "youtube" ? "YouTube" : "Local file"} · {v.has_subtitles ? (v.timed ? "synced subtitles" : "transcript") : "no subtitles yet"}{v.has_study ? " · study pack ready" : ""}</div></div>
            <LevelPill l={v.level} />
          </Link>
        ))}
        <div className="card text-sm">
          <div className="label">Good legal sources</div>
          <p className="muted">YouTube channels such as BBC Learning English, TED and TED-Ed, and university lecture channels; your own recordings; course videos you have the right to use. On YouTube, open “… › Show transcript”, copy it, and paste it into the transcript box. For perfect sync, use a .srt or .vtt subtitle file.</p>
        </div>
      </div>
      <form onSubmit={add} className="card space-y-3">
        <h2 className="font-semibold">Add a video</h2>
        <div className="flex gap-1"><button type="button" className={kind === "youtube" ? "btn-primary" : "btn-ghost"} onClick={() => setKind("youtube")}>YouTube link</button><button type="button" className={kind === "file" ? "btn-primary" : "btn-ghost"} onClick={() => setKind("file")}>Video file</button></div>
        <input className="input" placeholder="Title" required value={title} onChange={(e) => setTitle(e.target.value)} />
        {kind === "youtube" ? <input className="input" placeholder="https://www.youtube.com/watch?v=…" required value={url} onChange={(e) => setUrl(e.target.value)} />
          : <label className="block text-sm">Video (.mp4, .webm)<input type="file" accept=".mp4,.m4v,.webm" required className="mt-1 block text-xs" onChange={(e) => setVideo(e.target.files?.[0] ?? null)} /></label>}
        <label className="block text-sm">Subtitles (.srt / .vtt), recommended<input type="file" accept=".srt,.vtt" className="mt-1 block text-xs" onChange={(e) => setSubs(e.target.files?.[0] ?? null)} /></label>
        <textarea className="input min-h-[90px] text-xs" placeholder="…or paste a transcript (timestamps like 0:12 are fine; sync works best with subtitle files)" value={transcript} onChange={(e) => setTranscript(e.target.value)} />
        <select className="input" value={level} onChange={(e) => setLevel(e.target.value)}>{["B2", "C1", "C2"].map((l) => <option key={l}>{l}</option>)}</select>
        <ErrorBox msg={err} />
        <button className="btn-primary w-full" disabled={busy}>{busy ? "Adding…" : "Add to my library"}</button>
        <p className="text-xs text-ink-400">Files stay on this computer (%APPDATA%\EnglishMasteryAI\videos). Nothing is uploaded to the internet.</p>
      </form>
    </div>
  );
}

// ---------------------------------------------------------------- player abstraction
interface Ctl { time: () => number; seek: (t: number) => void; play: () => void; pause: () => void; rate: (r: number) => void }

declare global { interface Window { YT?: any; onYouTubeIframeAPIReady?: () => void } } // eslint-disable-line @typescript-eslint/no-explicit-any

function loadYT(): Promise<any> { // eslint-disable-line @typescript-eslint/no-explicit-any
  return new Promise((resolve) => {
    if (window.YT?.Player) return resolve(window.YT);
    window.onYouTubeIframeAPIReady = () => resolve(window.YT);
    if (!document.getElementById("yt-api")) {
      const s = Object.assign(document.createElement("script"), { id: "yt-api", src: "https://www.youtube.com/iframe_api" });
      document.body.appendChild(s);
    }
  });
}

export function VideoPlayerPage() {
  const { id } = useParams();
  const { profile } = useProfile();
  const [v, setV] = useState<VideoFull | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [active, setActive] = useState(-1);
  const [showSubs, setShowSubs] = useState(true);
  const [stopAfter, setStopAfter] = useState(false);
  const [speed, setSpeed] = useState(1);
  const ctl = useRef<Ctl | null>(null);
  const videoEl = useRef<HTMLVideoElement>(null);
  const ytHost = useRef<HTMLDivElement>(null);
  const stopAt = useRef<number | null>(null);
  const watched = useRef(0);

  const [fileSrc, setFileSrc] = useState<string | null>(null);
  useEffect(() => { api.get<VideoFull>(`/api/video/items/${id}`).then(setV).catch((e) => setErr(e.message)); }, [id]);
  useEffect(() => {
    if (!v || v.source !== "file") return;
    const url = previewVideoUrls[v.id] ?? `/api/video/items/${v.id}/file`;
    if (PREVIEW) playableUrl(url).then((u) => { previewVideoUrls[v.id] = u; setFileSrc(u); }).catch(() => setErr("Could not load the video file.")); else setFileSrc(url);
  }, [v?.id]); // eslint-disable-line

  // Wire up the player
  useEffect(() => {
    if (!v) return;
    if (v.source === "file" && videoEl.current && fileSrc) {
      const el = videoEl.current;
      ctl.current = { time: () => el.currentTime, seek: (t) => { el.currentTime = t; }, play: () => { el.play(); }, pause: () => el.pause(), rate: (r) => { el.playbackRate = r; } };
    }
    let player: any; // eslint-disable-line @typescript-eslint/no-explicit-any
    if (v.source === "youtube" && ytHost.current && !SANDBOXED) {
      loadYT().then((YT) => {
        player = new YT.Player(ytHost.current, { videoId: v.youtube_id, host: "https://www.youtube-nocookie.com", width: "100%", height: "100%", playerVars: { rel: 0, modestbranding: 1, cc_load_policy: 0 } });
        ctl.current = { time: () => player.getCurrentTime?.() ?? 0, seek: (t) => player.seekTo(t, true), play: () => player.playVideo(), pause: () => player.pauseVideo(), rate: (r) => player.setPlaybackRate(r) };
      });
    }
    const timer = window.setInterval(() => {
      const c = ctl.current;
      if (!c) return;
      const t = c.time();
      if (stopAt.current != null && t >= stopAt.current) { c.pause(); stopAt.current = null; }
      const idx = v.cues.findIndex((q) => q.start != null && t >= q.start && t < (q.end ?? q.start + 4));
      setActive(idx);
    }, 200);
    const start = Date.now();
    return () => {
      window.clearInterval(timer);
      player?.destroy?.();
      watched.current = Math.round((Date.now() - start) / 1000);
      if (watched.current > 30) api.post(`/api/video/items/${v.id}/progress`, { seconds: Math.min(watched.current, 36000) }).catch(() => {});
    };
  }, [v, fileSrc]);

  useEffect(() => { ctl.current?.rate(speed); }, [speed]);
  useEffect(() => { document.getElementById(`cue-${active}`)?.scrollIntoView({ block: "nearest", behavior: "smooth" }); }, [active]);

  function playCue(c: Cue) {
    if (c.start == null || !ctl.current) return;
    ctl.current.seek(c.start);
    stopAt.current = stopAfter && c.end != null ? c.end : null;
    ctl.current.play();
  }

  if (err) return <ErrorBox msg={err} />;
  if (!v) return <div className="text-ink-400">Loading…</div>;
  const cur = active >= 0 ? v.cues[active] : null;

  return (
    <div className="mx-auto grid max-w-7xl grid-cols-[1fr_380px] gap-6">
      <div className="space-y-4">
        <Link to="/video" className="text-sm text-brand-500">← Video Academy</Link>
        <div className="flex items-center gap-2"><LevelPill l={v.level} /><h1 className="font-serif text-2xl">{v.title}</h1><BookmarkButton kind="video" itemId={String(v.id)} title={v.title} route={`/video/${v.id}`} /></div>
        <div className="overflow-hidden rounded-2xl bg-black">
          <div className="relative aspect-video">
            {v.source === "file" ? <video ref={videoEl} src={fileSrc ?? undefined} controls className="h-full w-full" />
              : SANDBOXED ? <div className="grid h-full w-full place-items-center p-6 text-center text-sm text-white/70">YouTube can't play inside this embedded preview. Open the app's own web address to watch it here, synced with the transcript.</div>
              : <div ref={ytHost} className="h-full w-full" />}
          </div>
          {showSubs && <div className="min-h-[56px] px-6 py-3 text-center font-serif text-lg text-white">{cur?.text ?? ""}</div>}
        </div>
        <div className="flex flex-wrap items-center gap-4 text-sm">
          <label className="flex items-center gap-2"><input type="checkbox" checked={showSubs} onChange={(e) => setShowSubs(e.target.checked)} /> Subtitles</label>
          <label className="flex items-center gap-2"><input type="checkbox" checked={stopAfter} onChange={(e) => setStopAfter(e.target.checked)} /> Pause after each replayed sentence</label>
          <span className="flex items-center gap-1"><span className="label !mb-0 mr-1">Speed</span>{[0.75, 0.9, 1, 1.25].map((s) => <button key={s} onClick={() => setSpeed(s)} className={`rounded-lg px-2 py-1 ${speed === s ? "bg-brand-600 text-white" : "hover:bg-ink-100 dark:hover:bg-ink-800"}`}>{s}×</button>)}</span>
        </div>
        <StudyPack v={v} setV={setV} accent={profile.accent_preference} />
      </div>
      <aside className="card flex max-h-[calc(100vh-4rem)] flex-col !p-0">
        <div className="border-b border-ink-100 p-4 dark:border-ink-800"><h2 className="font-semibold">Interactive transcript</h2><p className="text-xs text-ink-400">{v.timed ? "Click a sentence to replay it." : v.cues.length ? "Transcript without timings: click 🔊 to hear a sentence." : "No subtitles yet."}</p></div>
        <div className="flex-1 overflow-y-auto p-2">
          {v.cues.map((c, i) => (
            <div key={i} id={`cue-${i}`} onClick={() => playCue(c)}
              className={`flex cursor-pointer items-start gap-2 rounded-lg px-3 py-2 text-sm ${i === active ? "bg-brand-50 dark:bg-brand-500/15" : "hover:bg-ink-50 dark:hover:bg-ink-800/50"}`}>
              {c.start != null && <span className="w-12 shrink-0 font-mono text-xs text-ink-400">{Math.floor(c.start / 60)}:{String(Math.floor(c.start % 60)).padStart(2, "0")}</span>}
              <span className="flex-1">{c.text}</span>
              <span onClick={(e) => e.stopPropagation()}><Speak text={c.text} accent={profile.accent_preference} /></span>
            </div>
          ))}
          {!v.cues.length && <AddSubs id={v.id} onDone={setV} />}
        </div>
      </aside>
    </div>
  );
}

function AddSubs({ id, onDone }: { id: number; onDone: (v: VideoFull) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [err, setErr] = useState<string | null>(null);
  async function save() {
    const fd = new FormData();
    if (file) fd.append("subtitles_file", file);
    fd.append("transcript", text);
    try { onDone(await api.upload<VideoFull>(`/api/video/items/${id}/subtitles`, fd)); } catch (e) { setErr((e as Error).message); }
  }
  return (
    <div className="space-y-2 p-2 text-sm">
      <input type="file" accept=".srt,.vtt" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="text-xs" />
      <textarea className="input min-h-[120px] text-xs" placeholder="…or paste the transcript" value={text} onChange={(e) => setText(e.target.value)} />
      <ErrorBox msg={err} />
      <button className="btn-primary w-full" disabled={!file && !text.trim()} onClick={save}>Add subtitles</button>
    </div>
  );
}

function StudyPack({ v, setV, accent }: { v: VideoFull; setV: (v: VideoFull) => void; accent: string }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<{ m: string; key: boolean } | null>(null);
  const [ans, setAns] = useState<Record<number, string>>({});
  const [summary, setSummary] = useState("");
  const [fb, setFb] = useState<{ improved_text: string; overall: number; issues: { original: string; corrected: string; explanation: string }[] } | null>(null);
  const s = v.study;

  async function generate() {
    setBusy(true); setErr(null);
    try { setV({ ...v, study: await api.post<Study>(`/api/video/items/${v.id}/study`), has_study: true }); }
    catch (e) { setErr({ m: (e as Error).message, key: (e as ApiError).status === 412 }); } finally { setBusy(false); }
  }
  async function sendSummary() {
    setBusy(true);
    try { setFb(await api.post("/api/writing/evaluate", { genre: "summary", text: summary, task: `Summarise the video "${v.title}". ${s?.summary_task ?? ""}` })); }
    catch (e) { setErr({ m: (e as Error).message, key: (e as ApiError).status === 412 }); } finally { setBusy(false); }
  }

  if (!s) return (
    <div className="card flex items-center justify-between">
      <div><h2 className="font-semibold">Study pack</h2><p className="muted">Vocabulary, idioms, grammar from the video, comprehension questions and pronunciation tips, generated from the subtitles.</p></div>
      <button className="btn-primary" disabled={busy || !v.cues.length} onClick={generate}>{busy ? "Preparing…" : "Create study pack"}</button>
      {err && <ErrorBox msg={err.m} action={err.key ? <Link to="/settings" className="underline">Settings</Link> : undefined} />}
    </div>
  );
  const correct = s.questions.filter((q, i) => ans[i] === q.answer).length;
  return (
    <div className="space-y-4">
      <div className="card"><div className="label">Summary</div><p>{s.summary}</p></div>
      <div className="grid grid-cols-2 gap-4">
        <div className="card"><div className="label">Vocabulary</div><ul className="space-y-2 text-sm">{s.vocabulary.map((w) => <li key={w.word}><span className="flex items-center gap-1 font-medium">{w.word}<Speak text={w.word} accent={accent} /></span><span className="text-ink-600 dark:text-ink-400">{w.meaning}</span>{w.french && <span className="text-ink-400"> · 🇫🇷 {w.french}</span>}<div className="italic text-ink-400">“{w.example}”</div></li>)}</ul></div>
        <div className="space-y-4">
          {s.idioms.length > 0 && <div className="card"><div className="label">Idioms & phrasal verbs</div><ul className="space-y-1 text-sm">{s.idioms.map((i) => <li key={i.phrase}><b>{i.phrase}</b> <span className="text-ink-400">— {i.meaning}</span></li>)}</ul></div>}
          {s.grammar.length > 0 && <div className="card"><div className="label">Grammar in context</div><ul className="space-y-2 text-sm">{s.grammar.map((g) => <li key={g.point}><b>{g.point}</b><div className="italic">“{g.example_from_video}”</div><div className="text-ink-400">{g.explanation}</div></li>)}</ul></div>}
          {s.pronunciation_focus.length > 0 && <div className="card"><div className="label">Pronunciation focus</div><ul className="space-y-1 text-sm">{s.pronunciation_focus.map((p) => <li key={p.phrase} className="flex items-start gap-1"><Speak text={p.phrase} accent={accent} /><span><b>{p.phrase}</b> <span className="text-ink-400">— {p.tip}</span></span></li>)}</ul></div>}
        </div>
      </div>
      <div className="card space-y-4">
        <div className="flex justify-between"><h2 className="font-semibold">Comprehension</h2>{Object.keys(ans).length > 0 && <span className="text-sm text-ink-400">{correct}/{Object.keys(ans).length}</span>}</div>
        {s.questions.map((q, i) => (
          <div key={i}><div className="mb-2 text-sm font-medium">{i + 1}. {q.prompt}</div>
            <div className="grid grid-cols-2 gap-2">{q.options.map((o) => (
              <button key={o} disabled={!!ans[i]} onClick={() => { const a = { ...ans, [i]: o }; setAns(a); if (Object.keys(a).length === s.questions.length) api.post(`/api/video/items/${v.id}/progress`, { seconds: 60, score: s.questions.filter((qq, k) => a[k] === qq.answer).length / s.questions.length, item: "quiz" }); }}
                className={`btn-ghost !justify-start text-left ${ans[i] && o === q.answer ? "!border-emerald-500" : ans[i] === o ? "!border-rose-500" : ""}`}>{o}</button>))}</div>
            {ans[i] && <p className="mt-1 text-sm text-ink-400">{q.explanation}</p>}
          </div>
        ))}
      </div>
      <div className="card space-y-3">
        <h2 className="font-semibold">Summary writing</h2><p className="muted">{s.summary_task}</p>
        <textarea className="input min-h-[120px] font-serif" value={summary} onChange={(e) => setSummary(e.target.value)} />
        <button className="btn-primary" disabled={busy || summary.trim().split(/\s+/).length < 15} onClick={sendSummary}>Get feedback</button>
        {fb && <div className="space-y-2 text-sm"><b>{Math.round(fb.overall * 100)}%</b><p className="rounded-xl bg-emerald-50 p-3 font-serif dark:bg-emerald-500/10">{fb.improved_text}</p>{fb.issues.map((i, k) => <p key={k}><span className="text-rose-500 line-through">{i.original}</span> → <span className="text-emerald-600">{i.corrected}</span> <span className="text-ink-400">{i.explanation}</span></p>)}</div>}
      </div>
      <div className="flex justify-end"><button className="btn-ghost" disabled={busy} onClick={() => api.post<Study>(`/api/video/items/${v.id}/study?refresh=true`).then((st) => setV({ ...v, study: st }))}>Regenerate study pack</button></div>
    </div>
  );
}

// ---------------------------------------------------------------- animated scenes
const COLORS = ["from-sky-500 to-blue-700", "from-amber-400 to-orange-600", "from-emerald-400 to-teal-700", "from-fuchsia-500 to-purple-700"];

export function AnimatedScene() {
  const { id } = useParams();
  const [it, setIt] = useState<Item | null>(null);
  const [cur, setCur] = useState(-1);
  const [subs, setSubs] = useState(true);
  const [speed, setSpeed] = useState(1);
  const player = useLinePlayer(it, speed);
  useEffect(() => { api.get<Item>(`/api/listening/items/${id}`).then(setIt); return () => player.stop(); }, [id]); // eslint-disable-line
  if (!it) return <div className="text-ink-400">Loading…</div>;
  const names = Object.keys(it.speakers);
  const line = cur >= 0 ? it.lines[cur] : null;
  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <Link to="/video" className="text-sm text-brand-500">← Video Academy</Link>
      <div className="flex items-center gap-2"><LevelPill l={it.level} /><h1 className="font-serif text-2xl">{it.title}</h1></div>
      <div className="overflow-hidden rounded-2xl bg-gradient-to-b from-ink-800 to-ink-950">
        <div className="flex h-72 items-end justify-center gap-16 px-10 pb-6">
          {names.map((n, i) => {
            const talking = line?.s === n;
            return (
              <div key={n} className={`flex flex-col items-center transition-transform duration-300 ${talking ? "-translate-y-2 scale-110" : "opacity-60"}`}>
                <div className={`relative grid h-28 w-28 place-items-center rounded-full bg-gradient-to-br ${COLORS[i % COLORS.length]} shadow-2xl ${talking ? "ring-4 ring-white/70" : ""}`}>
                  <div className="absolute top-9 flex gap-6"><span className="h-3 w-3 rounded-full bg-white" /><span className="h-3 w-3 rounded-full bg-white" /></div>
                  <span className={`absolute bottom-7 w-8 rounded-full bg-white/90 ${talking ? "animate-talk h-3" : "h-1"}`} />
                </div>
                <div className="mt-3 text-sm text-white">{n}</div><div className="text-xs text-white/50">{ACCENT_NAME[it.speakers[n].accent]}</div>
              </div>
            );
          })}
        </div>
        <div className="min-h-[64px] bg-black/60 px-8 py-4 text-center font-serif text-lg text-white">{subs && line ? line.t : ""}</div>
      </div>
      <div className="flex flex-wrap items-center gap-4 text-sm">
        {cur < 0 ? <button className="btn-primary" onClick={() => player.playFrom(0, it.lines.length - 1, setCur)}>▶ Play scene</button> : <button className="btn-primary !bg-rose-600" onClick={() => { player.stop(); setCur(-1); }}>■ Stop</button>}
        <label className="flex items-center gap-2"><input type="checkbox" checked={subs} onChange={(e) => setSubs(e.target.checked)} /> Subtitles</label>
        <span className="flex items-center gap-1">{[0.75, 0.9, 1].map((s) => <button key={s} onClick={() => setSpeed(s)} className={`rounded-lg px-2 py-1 ${speed === s ? "bg-brand-600 text-white" : ""}`}>{s}×</button>)}</span>
        <Link to={`/listening/${it.id}`} className="btn-ghost ml-auto">Exercises for this scene →</Link>
      </div>
      <div className="card space-y-1">{it.lines.map((l, i) => (
        <div key={i} onClick={() => { player.stop(); setTimeout(() => player.playFrom(i, i, setCur), 50); }} className={`flex cursor-pointer gap-3 rounded-lg px-3 py-1.5 text-sm ${cur === i ? "bg-brand-50 dark:bg-brand-500/15" : "hover:bg-ink-50 dark:hover:bg-ink-800/50"}`}>
          <span className="w-24 shrink-0 text-ink-400">{l.s}</span><span>{l.t}</span></div>
      ))}</div>
    </div>
  );
}
