import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../../lib/api";
import { ErrorBox, LevelPill } from "../../components/ui";
import { date, LEVELS } from "./AdminApp";

function Flash({ msg }: { msg: string | null }) {
  return msg ? <div className="rounded-xl bg-emerald-50 p-3 text-sm text-emerald-800 dark:bg-emerald-500/10 dark:text-emerald-300">{msg}</div> : null;
}

// ------------------------------------------------------------------ lessons
interface LessonRow { id: string; title: string; level: string; unit: string; summary: string; exercises: number; builtin: boolean; customised: boolean; published: boolean; deleted: boolean; collection: string }
const COLL: Record<string, string> = { grammar: "Grammar", lessons: "Communication", business: "Business English" };

export function LessonList() {
  const [rows, setRows] = useState<LessonRow[] | null>(null);
  const [coll, setColl] = useState("");
  const [q, setQ] = useState("");
  const [level, setLevel] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const load = () => api.get<LessonRow[]>(`/api/admin/content/lessons?collection=${coll}&q=${encodeURIComponent(q)}`).then(setRows).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, [coll]); // eslint-disable-line
  const act = (fn: () => Promise<unknown>) => fn().then(load).catch((e) => setErr(e.message));
  const shown = (rows ?? []).filter((r) => !level || r.level === level);
  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="h1">Lessons</h1><p className="muted mt-1">Built-in lessons can be edited, unpublished or hidden (and restored); new lessons are yours entirely. Add them to a level in <Link className="text-brand-500" to="/admin/content/curriculum">Levels & curriculum</Link>.</p></div>
        <Link to="/admin/content/lessons/new" className="btn-primary">+ New lesson</Link>
      </div>
      <ErrorBox msg={err} />
      <div className="flex flex-wrap gap-2">
        <form className="flex-1" onSubmit={(e) => { e.preventDefault(); load(); }}><input className="input" placeholder="Search lessons…" value={q} onChange={(e) => setQ(e.target.value)} /></form>
        <select className="input !w-48" value={coll} onChange={(e) => setColl(e.target.value)}><option value="">All collections</option>{Object.entries(COLL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
        <select className="input !w-32" value={level} onChange={(e) => setLevel(e.target.value)}><option value="">All levels</option>{LEVELS.map((l) => <option key={l}>{l}</option>)}</select>
      </div>
      <div className="card overflow-x-auto !p-0"><table className="w-full min-w-[760px] text-sm">
        <thead className="text-left text-xs uppercase text-ink-400"><tr>{["Lesson", "Level", "Collection", "Exercises", "Status", ""].map((h) => <th key={h} className="px-4 py-3">{h}</th>)}</tr></thead>
        <tbody>{shown.map((r) => (
          <tr key={r.id} className={`border-t border-ink-100 dark:border-ink-800 ${r.deleted ? "opacity-50" : ""}`}>
            <td className="px-4 py-2"><div className="font-medium">{r.title}</div><div className="text-xs text-ink-400">{r.id} · {r.builtin ? (r.customised ? "built-in, edited" : "built-in") : "custom"}</div></td>
            <td><LevelPill l={r.level} /></td><td>{COLL[r.collection]}</td><td>{r.exercises}</td>
            <td>{r.deleted ? "hidden" : r.published ? <span className="text-emerald-500">published</span> : <span className="text-amber-500">unpublished</span>}</td>
            <td className="space-x-2 whitespace-nowrap px-4 text-right">
              {!r.deleted && <Link className="text-brand-500" to={`/admin/content/lessons/${r.id}`}>Edit</Link>}
              {!r.deleted && <button className="text-brand-500" onClick={() => act(() => api.post(`/api/admin/content/lessons/${r.id}/publish`, { published: !r.published }))}>{r.published ? "Unpublish" : "Publish"}</button>}
              {r.builtin && (r.customised || r.deleted) && <button className="text-brand-500" onClick={() => act(() => api.post(`/api/admin/content/lessons/${r.id}/restore`))}>Restore original</button>}
              {!r.deleted && <button className="text-rose-500" onClick={() => { if (window.confirm(r.builtin ? "Hide this built-in lesson? You can restore it later." : "Delete this lesson permanently?")) act(() => api.del(`/api/admin/content/lessons/${r.id}`)); }}>{r.builtin ? "Hide" : "Delete"}</button>}
            </td></tr>))}</tbody></table></div>
    </div>
  );
}

interface Ex { id: string; type: string; prompt: string; options?: string[]; answer: string | string[]; explanation: string }
interface LessonDoc { id?: string; title: string; level: string; unit: string; summary: string; explanation: string; explanation_fr: string; examples: { en: string; note: string }[]; exercises: Ex[]; collection: string; published: boolean; builtin?: boolean }
const BLANK: LessonDoc = { title: "", level: "A1", unit: "", summary: "", explanation: "", explanation_fr: "", examples: [{ en: "", note: "" }], exercises: [{ id: "ex1", type: "mcq", prompt: "", options: ["", ""], answer: "", explanation: "" }], collection: "lessons", published: false };

export function LessonEditor() {
  const { id } = useParams();
  const isNew = id === "new";
  const nav = useNavigate();
  const [d, setD] = useState<LessonDoc | null>(isNew ? BLANK : null);
  const [lid, setLid] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => { if (!isNew) api.get<LessonDoc>(`/api/admin/content/lessons/${id}`).then((x) => setD({ ...BLANK, ...x, explanation_fr: x.explanation_fr ?? "", examples: x.examples?.length ? x.examples : [{ en: "", note: "" }] })).catch((e) => setErr(e.message)); }, [id]); // eslint-disable-line
  if (err && !d) return <ErrorBox msg={err} />;
  if (!d) return <div className="text-ink-400">Loading…</div>;
  const set = (k: keyof LessonDoc, v: unknown) => setD({ ...d, [k]: v });
  const setEx = (i: number, patch: Partial<Ex>) => set("exercises", d.exercises.map((e, k) => (k === i ? { ...e, ...patch } : e)));
  async function save() {
    setErr(null);
    const target = isNew ? lid.trim().toLowerCase() : id!;
    const body = { ...d, examples: d!.examples.filter((x) => x.en.trim()), exercises: d!.exercises.map((e) => ({ ...e, options: e.type === "mcq" ? e.options?.filter((o) => o.trim()) : undefined,
      answer: typeof e.answer === "string" ? (e.type === "mcq" ? e.answer : e.answer.split("|").map((a) => a.trim()).filter(Boolean)) : e.answer })) };
    try { await api.put(`/api/admin/content/lessons/${target}`, body); setMsg("Saved successfully."); if (isNew) nav(`/admin/content/lessons/${target}`, { replace: true }); }
    catch (e) { setErr((e as Error).message); }
  }
  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <Link to="/admin/content/lessons" className="text-sm text-brand-500">← Lessons</Link>
      <h1 className="h1">{isNew ? "New lesson" : `Edit: ${d.title}`}</h1>
      {d.builtin && <p className="text-sm text-ink-400">This is a built-in lesson. Your edits replace it for every learner; “Restore original” on the list undoes them.</p>}
      <Flash msg={msg} /><ErrorBox msg={err} />
      <div className="card grid gap-3 sm:grid-cols-2">
        {isNew && <div><label className="label">Lesson id (lowercase-dashes, permanent)</label><input className="input font-mono" placeholder="a2-ordering-food" value={lid} onChange={(e) => setLid(e.target.value)} /></div>}
        <div className={isNew ? "" : "sm:col-span-2"}><label className="label">Title</label><input className="input" value={d.title} onChange={(e) => set("title", e.target.value)} /></div>
        <div><label className="label">Level</label><select className="input" value={d.level} onChange={(e) => set("level", e.target.value)}>{LEVELS.map((l) => <option key={l}>{l}</option>)}</select></div>
        {isNew && <div><label className="label">Collection</label><select className="input" value={d.collection} onChange={(e) => set("collection", e.target.value)}><option value="lessons">Communication (General English)</option><option value="grammar">Grammar</option><option value="business">Business English Academy</option></select></div>}
        <div><label className="label">Unit / theme</label><input className="input" value={d.unit} onChange={(e) => set("unit", e.target.value)} /></div>
        <div className="sm:col-span-2"><label className="label">Summary (one line)</label><input className="input" value={d.summary} onChange={(e) => set("summary", e.target.value)} /></div>
        <div className="sm:col-span-2"><label className="label">Explanation (one paragraph per line)</label><textarea className="input min-h-[180px]" value={d.explanation} onChange={(e) => set("explanation", e.target.value)} /></div>
        <div className="sm:col-span-2"><label className="label">French note (optional)</label><textarea className="input" value={d.explanation_fr} onChange={(e) => set("explanation_fr", e.target.value)} /></div>
      </div>
      <div className="card space-y-2"><h2 className="font-semibold">Examples</h2>
        {d.examples.map((x, i) => <div key={i} className="grid gap-2 sm:grid-cols-[2fr_1fr_auto]"><input className="input" placeholder="English example" value={x.en} onChange={(e) => set("examples", d.examples.map((y, k) => (k === i ? { ...y, en: e.target.value } : y)))} />
          <input className="input" placeholder="Note" value={x.note} onChange={(e) => set("examples", d.examples.map((y, k) => (k === i ? { ...y, note: e.target.value } : y)))} />
          <button className="btn-ghost" onClick={() => set("examples", d.examples.filter((_, k) => k !== i))}>✕</button></div>)}
        <button className="btn-ghost" onClick={() => set("examples", [...d.examples, { en: "", note: "" }])}>+ Example</button>
      </div>
      <div className="card space-y-4"><h2 className="font-semibold">Exercises</h2>
        {d.exercises.map((x, i) => (
          <div key={i} className="space-y-2 border-t border-ink-100 pt-3 first:border-0 first:pt-0 dark:border-ink-800">
            <div className="grid gap-2 sm:grid-cols-[120px_160px_1fr_auto]">
              <input className="input font-mono" value={x.id} onChange={(e) => setEx(i, { id: e.target.value })} />
              <select className="input" value={x.type} onChange={(e) => setEx(i, { type: e.target.value, options: e.target.value === "mcq" ? x.options ?? ["", ""] : undefined })}><option value="mcq">Multiple choice</option><option value="gap">Fill the gap</option><option value="correct">Correct the sentence</option><option value="translate">Write / translate</option></select>
              <input className="input" placeholder="Prompt" value={x.prompt} onChange={(e) => setEx(i, { prompt: e.target.value })} />
              <button className="btn-ghost" onClick={() => set("exercises", d.exercises.filter((_, k) => k !== i))}>✕</button>
            </div>
            {x.type === "mcq" ? (
              <div className="flex flex-wrap gap-2">{(x.options ?? []).map((o, k) => (
                <label key={k} className="flex items-center gap-1"><input type="radio" checked={x.answer === o && o !== ""} onChange={() => setEx(i, { answer: o })} title="Correct answer" />
                  <input className="input !w-48" value={o} placeholder={`Option ${k + 1}`} onChange={(e) => { const opts = [...x.options!]; const was = opts[k]; opts[k] = e.target.value; setEx(i, { options: opts, answer: x.answer === was ? e.target.value : x.answer }); }} /></label>))}
                <button className="btn-ghost" onClick={() => setEx(i, { options: [...(x.options ?? []), ""] })}>+ option</button></div>
            ) : <input className="input" placeholder="Accepted answers, separated by |" value={Array.isArray(x.answer) ? x.answer.join(" | ") : x.answer} onChange={(e) => setEx(i, { answer: e.target.value })} />}
            <input className="input" placeholder="Explanation shown after answering" value={x.explanation} onChange={(e) => setEx(i, { explanation: e.target.value })} />
          </div>))}
        <button className="btn-ghost" onClick={() => set("exercises", [...d.exercises, { id: `ex${d.exercises.length + 1}`, type: "mcq", prompt: "", options: ["", ""], answer: "", explanation: "" }])}>+ Exercise</button>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={d.published} onChange={(e) => set("published", e.target.checked)} /> Published (visible to learners)</label>
        <button className="btn-primary" onClick={save}>Save lesson</button>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ curriculum
interface Item { kind: string; ref: string; title?: string; genre?: string; task?: string }
interface Cur { levels: { code: string; name: string; description: string; units: { title: string; items: Item[] }[] }[]; business: { id: string; title: string; icon: string; level: string; items: Item[] }[] }
interface CurResp { curriculum: Cur; customised: boolean; lessons: { id: string; title: string; level: string; published: boolean }[]; media: { id: number; title: string; kind: string; level: string | null }[];
  readings: { id: string; title: string; level: string }[]; listening: { id: string; title: string; level: string }[]; modes: { id: string; title: string }[]; writing_genres: string[] }
const KINDS: [string, string][] = [["lesson", "Lesson"], ["reading", "Reading"], ["listening", "Listening"], ["media", "Audio / video"], ["vocab", "Vocabulary set"], ["conversation", "AI conversation"], ["writing", "Writing task"], ["pronunciation", "Pronunciation"], ["soon", "Coming soon"]];

export function CurriculumEditor() {
  const [r, setR] = useState<CurResp | null>(null);
  const [cur, setCur] = useState<Cur | null>(null);
  const [tab, setTab] = useState("A1");
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const load = () => api.get<CurResp>("/api/admin/content/curriculum").then((x) => { setR(x); setCur(structuredClone(x.curriculum)); }).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);
  if (err && !cur) return <ErrorBox msg={err} />;
  if (!r || !cur) return <div className="text-ink-400">Loading…</div>;
  const title = (it: Item) => it.title || (it.kind === "lesson" ? r.lessons.find((l) => l.id === it.ref)?.title : it.kind === "reading" ? r.readings.find((x) => x.id === it.ref)?.title
    : it.kind === "listening" ? r.listening.find((x) => x.id === it.ref)?.title : it.kind === "media" ? r.media.find((m) => String(m.id) === String(it.ref))?.title : it.kind === "conversation" ? r.modes.find((m) => m.id === it.ref)?.title : it.ref) || it.ref;
  const lv = cur.levels.find((l) => l.code === tab);
  const biz = tab === "business";
  const mutate = (fn: (c: Cur) => void) => { const c = structuredClone(cur); fn(c); setCur(c); };
  const listsFor = biz ? cur.business.map((c) => ({ title: `${c.icon} ${c.title}`, items: c.items })) : lv!.units;
  async function save() { setErr(null); try { await api.put("/api/admin/content/curriculum", cur); setMsg("Curriculum saved — learners see it now."); load(); setTimeout(() => setMsg(null), 3000); } catch (e) { setErr((e as Error).message); } }
  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="h1">Levels & curriculum</h1><p className="muted mt-1">Organise each CEFR level's units and the Business Academy's categories. Lessons can only sit in their own level, and every activity appears once.</p></div>
        <div className="flex gap-2">{r.customised && <button className="btn-ghost" onClick={async () => { if (window.confirm("Discard all curriculum changes and go back to the original?")) { await api.del("/api/admin/content/curriculum"); load(); } }}>Reset to original</button>}<button className="btn-primary" onClick={save}>Save curriculum</button></div>
      </div>
      <Flash msg={msg} /><ErrorBox msg={err} />
      <div className="flex flex-wrap gap-1">{[...LEVELS, "business"].map((t) => <button key={t} className={tab === t ? "btn-primary" : "btn-ghost"} onClick={() => setTab(t)}>{t === "business" ? "Business Academy" : t}</button>)}</div>
      {lv && !biz && <div className="card grid gap-3 sm:grid-cols-[200px_1fr]"><div><label className="label">Level name</label><input className="input" value={lv.name} onChange={(e) => mutate((c) => { c.levels.find((x) => x.code === tab)!.name = e.target.value; })} /></div>
        <div><label className="label">Description / objectives</label><input className="input" value={lv.description} onChange={(e) => mutate((c) => { c.levels.find((x) => x.code === tab)!.description = e.target.value; })} /></div></div>}
      {listsFor.map((u, ui) => (
        <div key={ui} className="card space-y-2">
          <div className="flex items-center gap-2">
            {biz ? <h2 className="flex-1 font-semibold">{u.title}</h2> : <input className="input flex-1 font-semibold" value={u.title} onChange={(e) => mutate((c) => { c.levels.find((x) => x.code === tab)!.units[ui].title = e.target.value; })} />}
            {!biz && <><button className="btn-ghost" disabled={ui === 0} onClick={() => mutate((c) => { const us = c.levels.find((x) => x.code === tab)!.units; [us[ui - 1], us[ui]] = [us[ui], us[ui - 1]]; })}>↑</button>
              <button className="btn-ghost" onClick={() => { if (window.confirm("Remove this unit?")) mutate((c) => { c.levels.find((x) => x.code === tab)!.units.splice(ui, 1); }); }}>Remove unit</button></>}
          </div>
          {u.items.map((it, ii) => (
            <div key={ii} className="flex items-center gap-2 rounded-lg border border-ink-200 px-3 py-1.5 text-sm dark:border-ink-800">
              <span className="w-28 shrink-0 text-xs uppercase text-ink-400">{KINDS.find(([k]) => k === it.kind)?.[1]}</span><span className="flex-1 truncate">{title(it)}</span>
              <button className="text-ink-400 hover:text-brand-500" disabled={ii === 0} onClick={() => mutate((c) => { const arr = biz ? c.business[ui].items : c.levels.find((x) => x.code === tab)!.units[ui].items; [arr[ii - 1], arr[ii]] = [arr[ii], arr[ii - 1]]; })}>↑</button>
              <button className="text-rose-500" onClick={() => mutate((c) => { (biz ? c.business[ui].items : c.levels.find((x) => x.code === tab)!.units[ui].items).splice(ii, 1); })}>✕</button>
            </div>))}
          <AddItem r={r} level={biz ? null : tab} onAdd={(it) => mutate((c) => { (biz ? c.business[ui].items : c.levels.find((x) => x.code === tab)!.units[ui].items).push(it); })} />
        </div>))}
      {!biz && <button className="btn-ghost" onClick={() => mutate((c) => { const l = c.levels.find((x) => x.code === tab)!; l.units.push({ title: `Unit ${l.units.length + 1} · New unit`, items: [] }); })}>+ Add a unit</button>}
    </div>
  );
}

function AddItem({ r, level, onAdd }: { r: CurResp; level: string | null; onAdd: (it: Item) => void }) {
  const [kind, setKind] = useState("lesson");
  const [ref, setRef] = useState("");
  const [title, setTitle] = useState("");
  const [genre, setGenre] = useState("essay");
  const [task, setTask] = useState("");
  const opts: [string, string][] = kind === "lesson" ? r.lessons.filter((l) => !level || l.level === level).map((l) => [l.id, `${l.title}${l.published ? "" : " (unpublished)"}`])
    : kind === "reading" ? r.readings.filter((x) => !level || x.level === level).map((x) => [x.id, x.title])
    : kind === "listening" ? r.listening.filter((x) => !level || x.level === level).map((x) => [x.id, x.title])
    : kind === "media" ? r.media.filter((m) => !level || !m.level || m.level === level).map((m) => [String(m.id), `${m.title} (${m.kind})`])
    : kind === "conversation" ? r.modes.map((m) => [m.id, m.title])
    : kind === "vocab" ? [...LEVELS.map((l) => [`level:${l}`, `All ${l} words`] as [string, string])] : [];
  const needsRef = ["lesson", "reading", "listening", "media", "conversation", "vocab"].includes(kind);
  function add() {
    if (kind === "writing") { if (!task.trim() || !ref.trim()) return; onAdd({ kind, ref: ref.trim(), genre, title: title || "Writing task", task }); }
    else if (kind === "pronunciation") onAdd({ kind, ref: "pronunciation", title: title || "Pronunciation practice" });
    else if (kind === "soon") onAdd({ kind, ref: "", title: title || "Coming soon" });
    else { if (!ref) return; onAdd({ kind, ref, ...(title ? { title } : {}) }); }
    setRef(""); setTitle(""); setTask("");
  }
  return (
    <div className="flex flex-wrap gap-2 pt-1">
      <select className="input !w-40" value={kind} onChange={(e) => { setKind(e.target.value); setRef(""); }}>{KINDS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
      {needsRef && <select className="input !w-72" value={ref} onChange={(e) => setRef(e.target.value)}><option value="">Choose…</option>{opts.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>}
      {kind === "writing" && <><input className="input !w-40 font-mono" placeholder="task-id" value={ref} onChange={(e) => setRef(e.target.value)} />
        <select className="input !w-36" value={genre} onChange={(e) => setGenre(e.target.value)}>{r.writing_genres.map((g) => <option key={g}>{g}</option>)}</select>
        <input className="input !w-80" placeholder="Task instructions" value={task} onChange={(e) => setTask(e.target.value)} /></>}
      {(kind !== "lesson" && kind !== "reading" && kind !== "listening") && <input className="input !w-56" placeholder="Title shown (optional)" value={title} onChange={(e) => setTitle(e.target.value)} />}
      <button className="btn-ghost" onClick={add}>+ Add</button>
    </div>
  );
}

// ------------------------------------------------------------------ media
interface MediaRow { id: number; title: string; kind: string; level: string | null; category: string | null; description: string; size: number; youtube_id: string | null; external_url: string | null; has_file: boolean; subtitles: number; questions: unknown[]; published: boolean; created_at: string }

export function MediaLibrary() {
  const [rows, setRows] = useState<MediaRow[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const load = () => api.get<MediaRow[]>("/api/admin/media").then(setRows).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);
  async function upload(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault(); setErr(null); setBusy(true);
    const fd = new FormData(e.currentTarget);
    for (const k of ["file", "subtitles_file"]) { const f = fd.get(k); if (f instanceof File && !f.name) fd.delete(k); }
    try { await api.upload("/api/admin/media", fd); (e.target as HTMLFormElement).reset(); setMsg("Added. Now place it in a level from Levels & curriculum (type “Audio / video”)."); load(); }
    catch (x) { setErr((x as Error).message); } finally { setBusy(false); }
  }
  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div><h1 className="h1">Audio & video</h1><p className="muted mt-1">Add recordings, videos (YouTube links or files up to 25 MB), PDFs, subtitles, transcripts and comprehension questions. Use only media you have the right to share.</p></div>
      <Flash msg={msg} /><ErrorBox msg={err} />
      <form className="card grid gap-3 sm:grid-cols-2" onSubmit={upload}>
        <div><label className="label">Title</label><input name="title" className="input" required minLength={2} /></div>
        <div className="grid grid-cols-2 gap-2"><div><label className="label">Type</label><select name="kind" className="input"><option value="audio">Audio</option><option value="video">Video</option><option value="document">Document (PDF)</option></select></div>
          <div><label className="label">Level</label><select name="level" className="input"><option value="">Any / Business</option>{LEVELS.map((l) => <option key={l}>{l}</option>)}</select></div></div>
        <div><label className="label">YouTube link (or upload a file below)</label><input name="youtube_url" className="input" placeholder="https://www.youtube.com/watch?v=…" /></div>
        <div><label className="label">File (mp3, m4a, wav, ogg, mp4, webm, pdf · max 25 MB)</label><input name="file" type="file" accept=".mp3,.m4a,.wav,.ogg,.mp4,.webm,.pdf" className="mt-1 block text-xs" /></div>
        <div><label className="label">Subtitles (.srt / .vtt)</label><input name="subtitles_file" type="file" accept=".srt,.vtt" className="mt-1 block text-xs" /></div>
        <div><label className="label">Description</label><input name="description" className="input" /></div>
        <div className="sm:col-span-2"><label className="label">Transcript (plain text, or paste SRT/VTT to create subtitles)</label><textarea name="transcript" className="input min-h-[90px]" /></div>
        <div className="sm:col-span-2"><label className="label">Comprehension questions (JSON, optional)</label><textarea name="questions" className="input min-h-[70px] font-mono text-xs" placeholder='[{"prompt": "Where are they?", "options": ["At a café", "At home"], "answer": "At a café", "explanation": "…"}]' /></div>
        <div className="sm:col-span-2 flex justify-end"><button className="btn-primary" disabled={busy}>{busy ? "Uploading…" : "Add to the library"}</button></div>
      </form>
      <div className="card overflow-x-auto !p-0"><table className="w-full min-w-[700px] text-sm">
        <thead className="text-left text-xs uppercase text-ink-400"><tr>{["Title", "Type", "Level", "Source", "Subtitles", "Questions", "Status", ""].map((h) => <th key={h} className="px-4 py-3">{h}</th>)}</tr></thead>
        <tbody>{rows.map((m) => (
          <tr key={m.id} className="border-t border-ink-100 dark:border-ink-800">
            <td className="px-4 py-2"><div className="font-medium">{m.title}</div><div className="text-xs text-ink-400">#{m.id} · {date(m.created_at)}</div></td><td>{m.kind}</td><td>{m.level ?? "—"}</td>
            <td>{m.youtube_id ? "YouTube" : m.has_file ? `${(m.size / 1048576).toFixed(1)} MB` : "link"}</td><td>{m.subtitles || "—"}</td><td>{m.questions.length || "—"}</td>
            <td>{m.published ? <span className="text-emerald-500">published</span> : <span className="text-amber-500">hidden</span>}</td>
            <td className="space-x-2 whitespace-nowrap px-4 text-right"><Link className="text-brand-500" to={`/media/${m.id}`}>Preview</Link>
              <button className="text-brand-500" onClick={() => api.put(`/api/admin/media/${m.id}`, { published: !m.published }).then(load)}>{m.published ? "Unpublish" : "Publish"}</button>
              <button className="text-rose-500" onClick={() => { if (window.confirm("Delete this media permanently?")) api.del(`/api/admin/media/${m.id}`).then(load).catch((e) => setErr(e.message)); }}>Delete</button></td>
          </tr>))}
          {rows.length === 0 && <tr><td colSpan={8} className="px-4 py-6 text-center text-ink-400">No media yet.</td></tr>}</tbody></table></div>
    </div>
  );
}
