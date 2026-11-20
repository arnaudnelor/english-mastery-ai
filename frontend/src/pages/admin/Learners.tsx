import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../../lib/api";
import { CategoryPill, ErrorBox } from "../../components/ui";
import { BarChart } from "../../components/BarChart";
import type { User } from "../Auth";
import { date, dateTime, LEVELS, pct, Stat } from "./AdminApp";

interface Row {
  user_id: number; name: string; email: string; country: string | null; status: string; role: string; email_verified: boolean; registered: string;
  last_login: string | null; last_seen: string | null; level: string | null; completed: number; hours: number; average: number | null; placement_done: boolean;
}

const STATUS_CLS: Record<string, string> = { active: "text-emerald-500", inactive: "text-ink-400", suspended: "text-rose-500" };

export function LearnerList() {
  const [params, setParams] = useSearchParams();
  const [q, setQ] = useState(params.get("q") ?? "");
  const level = params.get("level") ?? "";
  const status = params.get("status") ?? "";
  const role = params.get("role") ?? "learner";
  const page = Number(params.get("page") ?? 1);
  const [d, setD] = useState<{ total: number; items: Row[] } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const set = (k: string, v: string) => { const p = new URLSearchParams(params); if (v) p.set(k, v); else p.delete(k); if (k !== "page") p.delete("page"); setParams(p); };
  useEffect(() => {
    const qs = new URLSearchParams({ q: params.get("q") ?? "", level, status, role, page: String(page), size: "25" });
    api.get<typeof d>(`/api/admin/learners?${qs}`).then(setD).catch((e) => setErr(e.message));
  }, [params]); // eslint-disable-line
  const exp = (fmt: string) => api.download(`/api/admin/reports/learners?format=${fmt}${level ? `&level=${level}` : ""}`, `learners.${fmt}`).catch((e) => setErr(e.message));
  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="h1">Learners</h1><p className="muted mt-1">{d ? `${d.total} account${d.total === 1 ? "" : "s"}` : "…"}</p></div>
        <div className="flex gap-2">{["csv", "xlsx", "pdf"].map((f) => <button key={f} className="btn-ghost" onClick={() => exp(f)}>⬇ {f.toUpperCase()}</button>)}</div>
      </div>
      <ErrorBox msg={err} />
      <div className="flex flex-wrap gap-2">
        <form className="flex-1" onSubmit={(e) => { e.preventDefault(); set("q", q.trim()); }}><input className="input" placeholder="Search by name or email…" value={q} onChange={(e) => setQ(e.target.value)} /></form>
        <select className="input !w-40" value={level} onChange={(e) => set("level", e.target.value)}><option value="">All levels</option>{LEVELS.map((l) => <option key={l}>{l}</option>)}<option value="none">Not placed</option></select>
        <select className="input !w-40" value={status} onChange={(e) => set("status", e.target.value)}><option value="">Any status</option><option value="active">Active</option><option value="inactive">Deactivated</option><option value="suspended">Suspended</option></select>
        <select className="input !w-44" value={role} onChange={(e) => set("role", e.target.value)}><option value="learner">Learners</option><option value="staff">Administrators</option></select>
      </div>
      <div className="card overflow-x-auto !p-0">
        <table className="w-full min-w-[860px] text-sm">
          <thead className="text-left text-xs uppercase text-ink-400"><tr>{["Learner", "Level", "Status", "Registered", "Last login", "Completed", "Hours", "Average"].map((h) => <th key={h} className="px-4 py-3">{h}</th>)}</tr></thead>
          <tbody>{d?.items.map((r) => (
            <tr key={r.user_id} className="border-t border-ink-100 hover:bg-ink-50 dark:border-ink-800 dark:hover:bg-ink-800/40">
              <td className="px-4 py-2"><Link className="font-medium hover:text-brand-500" to={`/admin/learners/${r.user_id}`}>{r.name}</Link><div className="text-xs text-ink-400">{r.email}{!r.email_verified && " · unconfirmed"}</div></td>
              <td>{r.level ?? <span className="text-ink-400">—</span>}</td><td className={`capitalize ${STATUS_CLS[r.status]}`}>{r.status}</td>
              <td>{date(r.registered)}</td><td>{date(r.last_login)}</td><td>{r.completed}</td><td>{r.hours}</td><td>{pct(r.average)}</td>
            </tr>))}
            {d && d.items.length === 0 && <tr><td colSpan={8} className="px-4 py-6 text-center text-ink-400">No accounts match.</td></tr>}</tbody>
        </table>
      </div>
      {d && d.total > 25 && <div className="flex justify-center gap-2"><button className="btn-ghost" disabled={page <= 1} onClick={() => set("page", String(page - 1))}>← Previous</button><span className="self-center text-sm">Page {page} / {Math.ceil(d.total / 25)}</span><button className="btn-ghost" disabled={page * 25 >= d.total} onClick={() => set("page", String(page + 1))}>Next →</button></div>}
    </div>
  );
}

interface Detail extends Row {
  first_name: string; last_name: string; preferred_language: string; objectives: string[]; target_level?: string; sessions: number; streak?: number;
  skills: Record<string, number | null>; vocabulary?: { total: number; mastered: number; due: number };
  assessments: { kind: string; level: string; score: number; passed: boolean; details: Record<string, unknown> | null; date: string }[];
  recent: { skill: string; item: string; score: number; date: string }[]; weaknesses: { category: string; pattern: string; count: number }[];
  weekly: { week: string; activities: number; average: number | null; minutes: number }[];
  lessons: { title: string; kind: string; level: string | null; status: string; score: number | null; date: string }[];
}

export function LearnerDetail({ me }: { me: User }) {
  const { id } = useParams();
  const [d, setD] = useState<Detail | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [link, setLink] = useState<{ link: string; emailed: boolean } | null>(null);
  const load = () => api.get<Detail>(`/api/admin/learners/${id}`).then(setD).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, [id]); // eslint-disable-line
  const act = async (fn: () => Promise<unknown>, m: string) => { setErr(null); try { await fn(); setMsg(m); load(); setTimeout(() => setMsg(null), 3000); } catch (e) { setErr((e as Error).message); } };
  if (err && !d) return <ErrorBox msg={err} />;
  if (!d) return <div className="text-ink-400">Loading…</div>;
  const can = (p: string) => me.role === "super_admin" || me.permissions.includes(p);
  const placement = d.assessments.find((a) => a.kind === "placement");
  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <Link to="/admin/learners" className="text-sm text-brand-500">← All learners</Link>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="h1">{d.name}</h1><p className="muted">{d.email} · {d.country ?? "—"} · language {d.preferred_language} · <span className={`capitalize ${STATUS_CLS[d.status]}`}>{d.status}</span>{d.role !== "learner" && ` · ${d.role.replace("_", " ")}`}</p></div>
        {can("learners.export") && <button className="btn-ghost" onClick={() => api.download(`/api/admin/learners/${d.user_id}/report.pdf`, `learner-${d.user_id}.pdf`)}>⬇ Individual report (PDF)</button>}
      </div>
      {msg && <div className="rounded-xl bg-emerald-50 p-3 text-sm text-emerald-800 dark:bg-emerald-500/10 dark:text-emerald-300">{msg}</div>}
      <ErrorBox msg={err} />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Stat label="Current level" value={d.level ?? "—"} sub={d.placement_done ? "placed by test" : d.level ? "chosen / promoted" : "not placed"} />
        <Stat label="Completed" value={d.completed} sub="activities" />
        <Stat label="Learning hours" value={d.hours} />
        <Stat label="Average score" value={pct(d.average)} />
        <Stat label="Streak" value={`${d.streak ?? 0} d`} sub={`${d.sessions} active session(s)`} />
      </div>
      <div className="grid gap-5 lg:grid-cols-3">
        <div className="card space-y-2"><h2 className="font-semibold">Skill scores</h2>
          {Object.entries(d.skills).map(([k, v]) => <div key={k} className="flex justify-between text-sm"><span className="capitalize">{k}</span><b>{pct(v)}</b></div>)}
          {d.vocabulary && <p className="text-xs text-ink-400">Vocabulary deck: {d.vocabulary.total} words, {d.vocabulary.mastered} mastered</p>}</div>
        <div className="card space-y-2"><h2 className="font-semibold">Placement test</h2>
          {placement ? <>
            <p className="font-serif text-2xl">{placement.level}</p><p className="text-xs text-ink-400">{date(placement.date)}</p>
            {placement.details && "skills" in placement.details && <p className="text-sm">{Object.entries(placement.details.skills as Record<string, string>).map(([k, v]) => `${k.replace("_", " & ")} ${v}`).join(" · ")}</p>}
            {placement.details && "weaknesses" in placement.details && (placement.details.weaknesses as string[]).length > 0 && <p className="text-xs text-amber-600 dark:text-amber-300">To work on: {(placement.details.weaknesses as string[]).join(", ")}</p>}
          </> : <p className="muted">Not taken yet.</p>}</div>
        <div className="card space-y-2"><h2 className="font-semibold">Weaknesses (recurring mistakes)</h2>
          {d.weaknesses.length === 0 ? <p className="muted">None recorded.</p> : d.weaknesses.map((w) => <div key={w.pattern} className="flex items-center justify-between gap-2 text-sm"><span className="flex items-center gap-2"><CategoryPill c={w.category} />{w.pattern}</span><span className="text-ink-400">×{w.count}</span></div>)}</div>
      </div>
      <div className="card"><h2 className="mb-2 font-semibold">Historical performance (12 weeks)</h2>
        <BarChart categories={d.weekly.map((w) => w.week.slice(5))} series={[{ name: "Study minutes", values: d.weekly.map((w) => w.minutes) }, { name: "Activities", values: d.weekly.map((w) => w.activities) }]} height={220} /></div>
      {can("learners.manage") && (
        <div className="card space-y-3"><h2 className="font-semibold">Account actions</h2>
          <div className="flex flex-wrap gap-2">
            {d.status !== "active" && <button className="btn-primary" onClick={() => act(() => api.post(`/api/admin/learners/${d.user_id}/status`, { status: "active" }), "Account activated.")}>Activate</button>}
            {d.status === "active" && <button className="btn-ghost" onClick={() => act(() => api.post(`/api/admin/learners/${d.user_id}/status`, { status: "inactive" }), "Account deactivated and signed out.")}>Deactivate</button>}
            {d.status !== "suspended" && <button className="btn-ghost !text-rose-500" onClick={() => { const reason = window.prompt("Reason for suspension (kept in the audit log):") ?? ""; act(() => api.post(`/api/admin/learners/${d.user_id}/status`, { status: "suspended", reason }), "Account suspended and signed out."); }}>Suspend</button>}
            {!d.email_verified && <button className="btn-ghost" onClick={() => act(() => api.post(`/api/admin/learners/${d.user_id}/verify`), "Email marked as confirmed.")}>Mark email confirmed</button>}
            <button className="btn-ghost" onClick={async () => { try { setLink(await api.post(`/api/admin/learners/${d.user_id}/reset-link`)); } catch (e) { setErr((e as Error).message); } }}>Create password-reset link</button>
            {can("users.roles") && d.user_id !== me.id && (
              <select className="input !w-56" value={d.role} onChange={(e) => { if (window.confirm(`Change role to ${e.target.value}?`)) act(() => api.post(`/api/admin/learners/${d.user_id}/role`, { role: e.target.value }), "Role changed."); }}>
                <option value="learner">Role: learner</option><option value="admin">Role: administrator</option>{me.role === "super_admin" && <option value="super_admin">Role: super administrator</option>}</select>)}
          </div>
          {link && <div className="rounded-xl bg-ink-50 p-3 text-sm dark:bg-ink-950">{link.emailed ? "The link was emailed to the learner. " : "Email isn't configured, so send this single-use link to the learner yourself (valid 72 hours): "}
            <div className="mt-1 flex gap-2"><input className="input font-mono text-xs" readOnly value={link.link} onFocus={(e) => e.target.select()} /><button className="btn-ghost" onClick={() => navigator.clipboard?.writeText(link.link)}>Copy</button></div></div>}
        </div>
      )}
      <div className="grid gap-5 lg:grid-cols-2">
        <div className="card"><h2 className="mb-2 font-semibold">Assessment results</h2>
          {d.assessments.length === 0 ? <p className="muted">None yet.</p> : <table className="w-full text-sm"><tbody>{d.assessments.map((a, i) => (
            <tr key={i} className="border-t border-ink-100 dark:border-ink-800"><td className="py-1.5">{date(a.date)}</td><td>{{ placement: "Placement", level_test: "Level test", business: "Business" }[a.kind] ?? a.kind}</td><td>{a.level}</td>
              <td>{a.kind === "placement" ? "" : pct(a.score)}</td><td className={a.passed ? "text-emerald-500" : "text-ink-400"}>{a.kind === "placement" ? "" : a.passed ? "passed" : "not passed"}</td></tr>))}</tbody></table>}</div>
        <div className="card"><h2 className="mb-2 font-semibold">Completed lessons & activities</h2>
          {d.lessons.length === 0 ? <p className="muted">None yet.</p> : <div className="max-h-80 overflow-y-auto"><table className="w-full text-sm"><tbody>{d.lessons.map((l, i) => (
            <tr key={i} className="border-t border-ink-100 dark:border-ink-800"><td className="py-1.5">{l.title}</td><td className="text-ink-400">{l.level}</td><td className={l.status === "completed" ? "text-emerald-500" : "text-ink-400"}>{l.status.replace("_", " ")}</td><td>{pct(l.score)}</td><td className="text-ink-400">{date(l.date)}</td></tr>))}</tbody></table></div>}</div>
      </div>
      <div className="card"><h2 className="mb-2 font-semibold">Recent activity</h2>
        <div className="max-h-72 overflow-y-auto"><table className="w-full text-sm"><tbody>{d.recent.map((a, i) => (
          <tr key={i} className="border-t border-ink-100 dark:border-ink-800"><td className="py-1.5 capitalize">{a.skill}</td><td className="text-ink-400">{a.item}</td><td>{pct(a.score)}</td><td className="text-ink-400">{dateTime(a.date)}</td></tr>))}</tbody></table></div></div>
      <div className="card text-sm"><h2 className="mb-2 font-semibold">Personal information</h2>
        <p>Registered {date(d.registered)} · last login {dateTime(d.last_login)} · last seen {dateTime(d.last_seen)}</p>
        <p>Objectives: {d.objectives.length ? d.objectives.join(", ") : "—"} · target level {d.target_level ?? "—"}</p></div>
    </div>
  );
}
