import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../lib/api";
import { ErrorBox } from "../../components/ui";
import { date, LEVELS, pct, Stat } from "./AdminApp";

interface Result { id: number; user_id: number; learner: string; kind: string; level: string; score: number; passed: boolean; details: Record<string, unknown> | null; date: string }
const KIND: Record<string, string> = { placement: "Placement test", level_test: "Level test", business: "Business assessment" };

export function AssessmentResults() {
  const [rows, setRows] = useState<Result[] | null>(null);
  const [kind, setKind] = useState("");
  const [level, setLevel] = useState("");
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { api.get<Result[]>(`/api/admin/assessments?kind=${kind}&level=${level}`).then(setRows).catch((e) => setErr(e.message)); }, [kind, level]);
  const pl = (rows ?? []).filter((r) => r.kind === "placement");
  const dist = LEVELS.map((l) => [l, pl.filter((r) => r.level === l).length] as const);
  const tests = (rows ?? []).filter((r) => r.kind !== "placement");
  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3"><div><h1 className="h1">Assessment results</h1><p className="muted mt-1">Every placement test, level test and Business assessment taken by learners.</p></div>
        <Link to="/admin/placement" className="btn-ghost">Configure the placement test</Link></div>
      <ErrorBox msg={err} />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Placement tests" value={pl.length} />
        <Stat label="Level / business tests" value={tests.length} sub={`${tests.filter((t) => t.passed).length} passed`} />
        <Stat label="Pass rate" value={tests.length ? pct(tests.filter((t) => t.passed).length / tests.length) : "—"} />
        <Stat label="Average test score" value={tests.length ? pct(tests.reduce((a, t) => a + t.score, 0) / tests.length) : "—"} />
      </div>
      {pl.length > 0 && <div className="card"><h2 className="mb-2 font-semibold">Placement results by CEFR level</h2><div className="flex flex-wrap gap-4 text-sm">{dist.map(([l, n]) => <span key={l}><b>{l}</b> {n}</span>)}</div></div>}
      <div className="flex gap-2"><select className="input !w-56" value={kind} onChange={(e) => setKind(e.target.value)}><option value="">All assessments</option>{Object.entries(KIND).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
        <select className="input !w-36" value={level} onChange={(e) => setLevel(e.target.value)}><option value="">All levels</option>{LEVELS.map((l) => <option key={l}>{l}</option>)}</select></div>
      <div className="card overflow-x-auto !p-0"><table className="w-full min-w-[720px] text-sm">
        <thead className="text-left text-xs uppercase text-ink-400"><tr>{["Date", "Learner", "Assessment", "Level", "Score", "Result", "Notes"].map((h) => <th key={h} className="px-4 py-3">{h}</th>)}</tr></thead>
        <tbody>{rows?.map((r) => (
          <tr key={r.id} className="border-t border-ink-100 dark:border-ink-800"><td className="px-4 py-2">{date(r.date)}</td><td><Link className="hover:text-brand-500" to={`/admin/learners/${r.user_id}`}>{r.learner}</Link></td>
            <td>{KIND[r.kind] ?? r.kind}</td><td>{r.level}</td><td>{r.kind === "placement" ? "—" : pct(r.score)}</td><td className={r.passed ? "text-emerald-500" : "text-ink-400"}>{r.kind === "placement" ? `placed ${r.level}` : r.passed ? "passed" : "not passed"}</td>
            <td className="max-w-xs truncate text-xs text-ink-400">{r.details && "weak_topics" in r.details ? `revise: ${(r.details.weak_topics as string[]).join(", ")}` : r.details && "skills" in r.details ? Object.entries(r.details.skills as Record<string, string>).map(([k, v]) => `${k.split("_")[0]} ${v}`).join(" · ") : ""}</td></tr>))}
          {rows?.length === 0 && <tr><td colSpan={7} className="px-4 py-6 text-center text-ink-400">No results yet.</td></tr>}</tbody></table></div>
    </div>
  );
}

interface Q { id: string; level: string; skill: string; prompt: string; options: string[]; answer: string }
interface PlacementDoc { grammar_vocab: Q[]; reading_text: string; listening_items: string[]; writing_prompt: string; speaking_prompt: string }
interface Cfg { document: PlacementDoc; customised: boolean; thresholds: { placement_level_threshold: number; level_test_pass_mark: number }; reading_options: string[]; listening_options: string[] }

export function PlacementConfig() {
  const [c, setC] = useState<Cfg | null>(null);
  const [doc, setDoc] = useState<PlacementDoc | null>(null);
  const [th, setTh] = useState({ placement_level_threshold: 0.6, level_test_pass_mark: 0.7 });
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const load = () => api.get<Cfg>("/api/admin/placement").then((x) => { setC(x); setDoc(structuredClone(x.document)); setTh(x.thresholds); }).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);
  if (!c || !doc) return err ? <ErrorBox msg={err} /> : <div className="text-ink-400">Loading…</div>;
  const setQ = (i: number, p: Partial<Q>) => setDoc({ ...doc, grammar_vocab: doc.grammar_vocab.map((q, k) => (k === i ? { ...q, ...p } : q)) });
  async function save() { setErr(null); try { await api.put("/api/admin/placement", { ...doc, ...th }); setMsg("Saved successfully. New placement tests use these questions now."); load(); } catch (e) { setErr((e as Error).message); } }
  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3"><div><h1 className="h1">Placement test</h1><p className="muted mt-1">Questions, sections and proficiency thresholds. Every level needs at least one question.</p></div>
        <div className="flex gap-2">{c.customised && <button className="btn-ghost" onClick={async () => { if (window.confirm("Restore the original placement test?")) { await api.del("/api/admin/placement"); load(); } }}>Restore original</button>}<button className="btn-primary" onClick={save}>Save</button></div></div>
      {msg && <div className="rounded-xl bg-emerald-50 p-3 text-sm text-emerald-800 dark:bg-emerald-500/10 dark:text-emerald-300">{msg}</div>}
      <ErrorBox msg={err} />
      <div className="card grid gap-3 sm:grid-cols-2">
        <div><label className="label">Level threshold: share of a level's questions needed to reach it ({Math.round(th.placement_level_threshold * 100)}%)</label><input type="range" min={0.3} max={0.95} step={0.05} className="w-full" value={th.placement_level_threshold} onChange={(e) => setTh({ ...th, placement_level_threshold: +e.target.value })} /></div>
        <div><label className="label">Level-test pass mark for promotion ({Math.round(th.level_test_pass_mark * 100)}%)</label><input type="range" min={0.4} max={0.95} step={0.05} className="w-full" value={th.level_test_pass_mark} onChange={(e) => setTh({ ...th, level_test_pass_mark: +e.target.value })} /></div>
        <div><label className="label">Reading section text</label><select className="input" value={doc.reading_text.split(":").pop()} onChange={(e) => setDoc({ ...doc, reading_text: `reading:${e.target.value}` })}>{c.reading_options.map((o) => <option key={o}>{o}</option>)}</select></div>
        <div><label className="label">Listening recordings (Ctrl-click for several)</label><select multiple className="input h-24" value={doc.listening_items} onChange={(e) => setDoc({ ...doc, listening_items: [...e.target.selectedOptions].map((o) => o.value) })}>{c.listening_options.map((o) => <option key={o}>{o}</option>)}</select></div>
        <div><label className="label">Writing prompt</label><textarea className="input" value={doc.writing_prompt} onChange={(e) => setDoc({ ...doc, writing_prompt: e.target.value })} /></div>
        <div><label className="label">Speaking prompt</label><textarea className="input" value={doc.speaking_prompt} onChange={(e) => setDoc({ ...doc, speaking_prompt: e.target.value })} /></div>
      </div>
      <div className="card space-y-3"><h2 className="font-semibold">Grammar, vocabulary & sentence-construction questions ({doc.grammar_vocab.length})</h2>
        {doc.grammar_vocab.map((q, i) => (
          <div key={i} className="space-y-1.5 border-t border-ink-100 pt-3 first:border-0 first:pt-0 dark:border-ink-800">
            <div className="grid gap-2 sm:grid-cols-[90px_80px_140px_1fr_auto]">
              <input className="input font-mono" value={q.id} onChange={(e) => setQ(i, { id: e.target.value })} />
              <select className="input" value={q.level} onChange={(e) => setQ(i, { level: e.target.value })}>{LEVELS.map((l) => <option key={l}>{l}</option>)}</select>
              <select className="input" value={q.skill ?? "grammar"} onChange={(e) => setQ(i, { skill: e.target.value })}><option value="grammar">Grammar</option><option value="vocabulary">Vocabulary</option><option value="construction">Sentence construction</option></select>
              <input className="input" value={q.prompt} onChange={(e) => setQ(i, { prompt: e.target.value })} />
              <button className="btn-ghost" onClick={() => setDoc({ ...doc, grammar_vocab: doc.grammar_vocab.filter((_, k) => k !== i) })}>Remove</button>
            </div>
            <div className="flex flex-wrap gap-2">{q.options.map((o, k) => (
              <label key={k} className="flex items-center gap-1"><input type="radio" checked={q.answer === o} onChange={() => setQ(i, { answer: o })} title="Correct answer" />
                <input className="input !w-56" value={o} onChange={(e) => { const opts = [...q.options]; opts[k] = e.target.value; setQ(i, { options: opts, answer: q.answer === o ? e.target.value : q.answer }); }} /></label>))}
              <button className="btn-ghost" onClick={() => setQ(i, { options: [...q.options, ""] })}>+ option</button></div>
          </div>))}
        <button className="btn-ghost" onClick={() => setDoc({ ...doc, grammar_vocab: [...doc.grammar_vocab, { id: `q${Date.now() % 100000}`, level: "B1", skill: "grammar", prompt: "", options: ["", ""], answer: "" }] })}>+ Add a question</button>
      </div>
    </div>
  );
}
