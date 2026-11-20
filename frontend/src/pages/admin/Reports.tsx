import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { ErrorBox } from "../../components/ui";
import { LEVELS } from "./AdminApp";

export default function Reports() {
  const [kinds, setKinds] = useState<Record<string, string>>({});
  const [kind, setKind] = useState("learners");
  const [f, setF] = useState({ date_from: "", date_to: "", level: "", course: "", learner: "" });
  const [learners, setLearners] = useState<{ user_id: number; name: string }[]>([]);
  const [data, setData] = useState<{ title: string; columns: string[]; rows: (string | number)[][] } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { api.get<Record<string, string>>("/api/admin/reports").then(setKinds); api.get<{ items: { user_id: number; name: string }[] }>("/api/admin/learners?size=200").then((r) => setLearners(r.items)); }, []);
  const qs = (fmt: string) => new URLSearchParams({ format: fmt, ...Object.fromEntries(Object.entries(f).filter(([, v]) => v)) }).toString();
  useEffect(() => { setErr(null); api.get<typeof data>(`/api/admin/reports/${kind}?${qs("json")}`).then(setData).catch((e) => setErr(e.message)); }, [kind, f]); // eslint-disable-line
  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div><h1 className="h1">Reports & exports</h1><p className="muted mt-1">Preview any report, then export it as Excel, CSV or PDF. Exports are recorded in the audit log.</p></div>
      <ErrorBox msg={err} />
      <div className="card grid gap-3 md:grid-cols-6">
        <div className="md:col-span-2"><label className="label">Report</label><select className="input" value={kind} onChange={(e) => setKind(e.target.value)}>{Object.entries(kinds).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></div>
        <div><label className="label">From</label><input type="date" className="input" value={f.date_from} onChange={(e) => setF({ ...f, date_from: e.target.value })} /></div>
        <div><label className="label">To</label><input type="date" className="input" value={f.date_to} onChange={(e) => setF({ ...f, date_to: e.target.value })} /></div>
        <div><label className="label">Level</label><select className="input" value={f.level} onChange={(e) => setF({ ...f, level: e.target.value })}><option value="">All</option>{LEVELS.map((l) => <option key={l}>{l}</option>)}</select></div>
        <div><label className="label">Course</label><select className="input" value={f.course} onChange={(e) => setF({ ...f, course: e.target.value })}><option value="">All</option>{LEVELS.map((l) => <option key={l} value={l}>General English {l}</option>)}<option value="business">Business English Academy</option></select></div>
        <div className="md:col-span-2"><label className="label">Learner</label><select className="input" value={f.learner} onChange={(e) => setF({ ...f, learner: e.target.value })}><option value="">All learners</option>{learners.map((l) => <option key={l.user_id} value={l.user_id}>{l.name}</option>)}</select></div>
        <div className="flex items-end gap-2 md:col-span-4">{[["xlsx", "Excel"], ["csv", "CSV"], ["pdf", "PDF"]].map(([k, l]) => <button key={k} className="btn-primary" onClick={() => api.download(`/api/admin/reports/${kind}?${qs(k)}`, `${kind}.${k}`).catch((e) => setErr(e.message))}>⬇ {l}</button>)}</div>
      </div>
      {data && <div className="card overflow-x-auto !p-0"><table className="w-full text-sm">
        <thead className="text-left text-xs uppercase text-ink-400"><tr>{data.columns.map((c) => <th key={c} className="px-4 py-3">{c}</th>)}</tr></thead>
        <tbody>{data.rows.map((r, i) => <tr key={i} className="border-t border-ink-100 dark:border-ink-800">{r.map((v, k) => <td key={k} className="px-4 py-1.5">{String(v)}</td>)}</tr>)}
          {data.rows.length === 0 && <tr><td colSpan={data.columns.length} className="px-4 py-6 text-center text-ink-400">No records for these filters.</td></tr>}</tbody></table></div>}
    </div>
  );
}
