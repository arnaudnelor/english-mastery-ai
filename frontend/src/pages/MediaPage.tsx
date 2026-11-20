import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../lib/api";
import { ErrorBox, LevelPill } from "../components/ui";

interface Cue { start: number; end: number; text: string }
interface Media {
  id: number; title: string; kind: "audio" | "video" | "document"; level: string | null; description: string; mime: string | null;
  has_file: boolean; youtube_id: string | null; external_url: string | null; cues: Cue[]; transcript: string;
  questions: { id: string; prompt: string; options: string[] }[];
}

/** Audio/video/document added by the academy, with synced subtitles, transcript and comprehension questions. */
export default function MediaPage() {
  const { id } = useParams();
  const [m, setM] = useState<Media | null>(null);
  const [src, setSrc] = useState<string | null>(null);
  const [t, setT] = useState(0);
  const [showSubs, setShowSubs] = useState(true);
  const [rate, setRate] = useState(1);
  const [ans, setAns] = useState<Record<string, string>>({});
  const [res, setRes] = useState<{ score: number; review: { id: string; correct: boolean; answer: string; explanation: string }[] } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const player = useRef<HTMLMediaElement | null>(null);
  useEffect(() => {
    api.get<Media>(`/api/media/${id}`).then((x) => {
      setM(x);
      if (x.has_file) api.blob(`/api/media/${id}/file`).then((b) => setSrc(URL.createObjectURL(b))).catch((e) => setErr(e.message));
    }).catch((e) => setErr(e.message));
  }, [id]);
  useEffect(() => { if (player.current) player.current.playbackRate = rate; }, [rate, src]);
  if (err) return <ErrorBox msg={err} />;
  if (!m) return <div className="text-ink-400">Loading…</div>;
  const cue = m.cues.find((c) => t >= c.start && t <= c.end);
  const bind = (el: HTMLMediaElement | null) => { player.current = el; };
  const back = m.level ? `/level/${m.level}` : "/";
  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <Link to={back} className="text-sm text-brand-500">← {m.level ? `${m.level} level dashboard` : "Dashboard"}</Link>
      <div><div className="flex items-center gap-2">{m.level && <LevelPill l={m.level} />}<span className="text-xs uppercase text-ink-400">{m.kind}</span></div><h1 className="h1 mt-2">{m.title}</h1>{m.description && <p className="muted mt-1">{m.description}</p>}</div>
      <div className="card space-y-3">
        {m.youtube_id ? (
          <div className="aspect-video overflow-hidden rounded-xl"><iframe className="h-full w-full" src={`https://www.youtube-nocookie.com/embed/${m.youtube_id}?cc_load_policy=1&rel=0`} title={m.title} allow="encrypted-media; picture-in-picture" allowFullScreen /></div>
        ) : m.kind === "document" ? (
          src ? <a className="btn-primary" href={src} download={`${m.title}.pdf`}>⬇ Open the document</a> : m.external_url ? <a className="btn-primary" href={m.external_url} target="_blank" rel="noreferrer">Open the resource ↗</a> : <p className="muted">Loading…</p>
        ) : m.has_file ? (
          !src ? <p className="muted">Loading the recording…</p> : m.kind === "video"
            ? <video ref={bind} src={src} controls className="w-full rounded-xl" onTimeUpdate={(e) => setT(e.currentTarget.currentTime)} />
            : <audio ref={bind} src={src} controls className="w-full" onTimeUpdate={(e) => setT(e.currentTarget.currentTime)} />
        ) : m.external_url ? <a className="btn-primary" href={m.external_url} target="_blank" rel="noreferrer">Open the recording ↗</a> : null}
        {m.has_file && m.kind !== "document" && (
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="label !mb-0">Speed</span>{[0.75, 0.9, 1, 1.25].map((r) => <button key={r} className={rate === r ? "btn-primary !py-1" : "btn-ghost !py-1"} onClick={() => setRate(r)}>{r}×</button>)}
            <button className="btn-ghost !py-1" onClick={() => { if (player.current) player.current.currentTime = Math.max(0, player.current.currentTime - 5); }}>⟲ 5 s</button>
            {m.cues.length > 0 && <label className="ml-auto flex items-center gap-1"><input type="checkbox" checked={showSubs} onChange={(e) => setShowSubs(e.target.checked)} /> Subtitles</label>}
          </div>
        )}
        {showSubs && m.cues.length > 0 && <div className="min-h-[3rem] rounded-xl bg-ink-50 p-3 text-center font-medium dark:bg-ink-950">{cue?.text ?? ""}</div>}
      </div>
      {(m.cues.length > 0 || m.transcript) && (
        <details className="card"><summary className="cursor-pointer font-semibold">Transcript</summary>
          <div className="mt-3 space-y-1 text-sm leading-relaxed">{m.cues.length ? m.cues.map((c, i) => (
            <button key={i} className={`block text-left ${cue === c ? "text-brand-500" : ""}`} onClick={() => { if (player.current) { player.current.currentTime = c.start; player.current.play(); } }}>{c.text}</button>
          )) : m.transcript.split("\n").map((l, i) => <p key={i}>{l}</p>)}</div>
        </details>
      )}
      <div className="card space-y-4">
        <h2 className="font-semibold">{m.questions.length ? "Comprehension questions" : "Finished?"}</h2>
        {m.questions.map((q, n) => {
          const r = res?.review.find((x) => x.id === q.id);
          return (
            <div key={q.id}><div className="mb-2 text-sm font-medium">{n + 1}. {q.prompt}</div>
              <div className="flex flex-wrap gap-2">{q.options.map((o) => <button key={o} disabled={!!res} className={`btn-ghost ${ans[q.id] === o ? (r ? (r.correct ? "!border-emerald-500" : "!border-rose-500") : "!border-brand-500") : ""}`} onClick={() => setAns((a) => ({ ...a, [q.id]: o }))}>{o}</button>)}</div>
              {r && !r.correct && <p className="mt-1 text-sm text-rose-500">Answer: {r.answer}. {r.explanation}</p>}</div>
          );
        })}
        {res ? <p className="font-medium">Saved · score {Math.round(res.score * 100)}%. <Link className="text-brand-500" to={back}>Back to the programme →</Link></p>
          : <button className="btn-primary" disabled={m.questions.some((q) => !ans[q.id])} onClick={async () => { try { setRes(await api.post(`/api/media/${id}/complete`, { answers: ans })); } catch (e) { setErr((e as Error).message); } }}>{m.questions.length ? "Check my answers" : "Mark as completed"}</button>}
      </div>
    </div>
  );
}
