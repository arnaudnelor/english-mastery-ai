import { useEffect, useState } from "react";
import { Link, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { api } from "../../lib/api";
import { ErrorBox } from "../../components/ui";
import { SaveIndicator, NotificationBell } from "../../components/Platform";
import type { User } from "../Auth";
import { LearnerDetail, LearnerList } from "./Learners";
import { CurriculumEditor, LessonEditor, LessonList, MediaLibrary } from "./Content";
import { AssessmentResults, PlacementConfig } from "./Assess";
import Reports from "./Reports";
import { AuditLog, Commercial, Integrations, PlatformSettings, RolesAndStaff } from "./System";

export const LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"];
export const pct = (v: number | null | undefined) => (v == null ? "—" : `${Math.round(v * 100)}%`);
export const date = (s: string | null | undefined) => (s ? new Date(s + (s.endsWith("Z") ? "" : "Z")).toLocaleDateString() : "—");
export const dateTime = (s: string | null | undefined) => (s ? new Date(s + (s.endsWith("Z") ? "" : "Z")).toLocaleString() : "—");

const NAV: [string, string, string?][] = [
  ["/admin", "Overview"], ["/admin/learners", "Learners"], ["/admin/assessments", "Assessment results"], ["/admin/reports", "Reports & exports"],
  ["/admin/content/lessons", "Lessons", "content.manage"], ["/admin/content/curriculum", "Levels & curriculum", "content.manage"], ["/admin/content/media", "Audio & video", "content.manage"],
  ["/admin/placement", "Placement test", "assessments.manage"], ["/admin/staff", "Administrators & roles"], ["/admin/settings", "Platform settings", "settings.manage"],
  ["/admin/integrations", "AI, email & status", "settings.manage"], ["/admin/audit", "Audit log", "audit.view"], ["/admin/commercial", "Plans & expansion", "plans.manage"],
];

export function AdminApp({ user, onSignOut }: { user: User; onSignOut: () => void }) {
  const [menu, setMenu] = useState(false);
  const loc = useLocation();
  useEffect(() => setMenu(false), [loc.pathname]);
  const can = (p?: string) => !p || user.role === "super_admin" || user.permissions.includes(p);
  return (
    <div className="flex h-screen overflow-hidden">
      {menu && <div className="fixed inset-0 z-30 bg-black/40 lg:hidden" onClick={() => setMenu(false)} />}
      <aside className={`fixed inset-y-0 left-0 z-40 flex w-64 shrink-0 flex-col border-r border-ink-200/70 bg-white transition-transform dark:border-ink-800 dark:bg-ink-900 lg:static lg:translate-x-0 ${menu ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="flex items-start justify-between px-6 pb-4 pt-6">
          <div><div className="font-serif text-xl leading-tight">English Mastery <span className="text-gold-500">AI</span></div>
            <div className="mt-1 text-xs font-semibold uppercase tracking-widest text-gold-500">Administrator portal</div></div>
          <NotificationBell />
        </div>
        <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 pb-4">
          {NAV.filter(([, , p]) => can(p)).map(([to, label]) => (
            <NavLink key={to} to={to} end={to === "/admin"} className={({ isActive }) => `block rounded-lg px-3 py-2 text-sm ${isActive ? "bg-brand-50 font-medium text-brand-700 dark:bg-brand-500/15 dark:text-brand-100" : "text-ink-800 hover:bg-ink-50 dark:text-ink-200 dark:hover:bg-ink-800/50"}`}>{label}</NavLink>
          ))}
        </nav>
        <div className="space-y-1 border-t border-ink-200/70 px-6 py-4 text-xs text-ink-400 dark:border-ink-800">
          <div className="truncate text-ink-800 dark:text-ink-100">{user.first_name} {user.last_name}</div>
          <div>{user.role === "super_admin" ? "Super Administrator" : "Administrator"}</div>
          <div className="flex gap-3"><Link to="/" className="text-brand-500">Learner view</Link><button className="hover:text-rose-500" onClick={onSignOut}>Sign out</button></div>
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto p-4 pt-16 sm:p-6 sm:pt-16 lg:p-8">
        <button className="fixed left-3 top-3 z-20 rounded-lg border border-ink-200 bg-white px-3 py-1.5 text-sm shadow dark:border-ink-800 dark:bg-ink-900 lg:hidden" onClick={() => setMenu(true)}>☰ Menu</button>
        <Routes>
          <Route path="/admin" element={<Overview />} />
          <Route path="/admin/learners" element={<LearnerList />} />
          <Route path="/admin/learners/:id" element={<LearnerDetail me={user} />} />
          <Route path="/admin/assessments" element={<AssessmentResults />} />
          <Route path="/admin/reports" element={<Reports />} />
          <Route path="/admin/content/lessons" element={<LessonList />} />
          <Route path="/admin/content/lessons/:id" element={<LessonEditor />} />
          <Route path="/admin/content/curriculum" element={<CurriculumEditor />} />
          <Route path="/admin/content/media" element={<MediaLibrary />} />
          <Route path="/admin/placement" element={<PlacementConfig />} />
          <Route path="/admin/staff" element={<RolesAndStaff me={user} />} />
          <Route path="/admin/settings" element={<PlatformSettings />} />
          <Route path="/admin/integrations" element={<Integrations />} />
          <Route path="/admin/audit" element={<AuditLog />} />
          <Route path="/admin/commercial" element={<Commercial />} />
          <Route path="*" element={<p>Not found. <Link className="text-brand-500" to="/admin">Overview</Link></p>} />
        </Routes>
      </main>
      <SaveIndicator />
    </div>
  );
}
export default AdminApp;

interface OverviewData {
  learners: { total: number; active: number; inactive: number; new_7d: number; new_30d: number; suspended: number; unverified: number };
  lessons_completed: number; learning_hours: number; average_performance_30d: number | null; cefr_distribution: Record<string, number>;
  business_enrolments: number; placement: { taken: number; learners_placed: number; distribution: Record<string, number> };
  recent: { learner: string; user_id: number; skill: string; item: string; score: number; date: string }[];
  attention: { user_id: number; name: string; email: string; reasons: string[] }[]; inactive_after_days: number; email_enabled: boolean; ai_enabled: boolean;
}

export function Stat({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return <div className="card !p-4"><div className="label">{label}</div><div className="font-serif text-3xl">{value}</div>{sub && <div className="text-xs text-ink-400">{sub}</div>}</div>;
}

function Overview() {
  const [d, setD] = useState<OverviewData | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { api.get<OverviewData>("/api/admin/overview").then(setD).catch((e) => setErr(e.message)); }, []);
  if (err) return <ErrorBox msg={err} />;
  if (!d) return <div className="text-ink-400">Loading…</div>;
  const maxDist = Math.max(1, ...Object.values(d.cefr_distribution));
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div><h1 className="h1">Academy overview</h1><p className="muted mt-1">Live figures from the database. “Active” means seen in the last {d.inactive_after_days} days.</p></div>
      {(!d.ai_enabled || !d.email_enabled) && (
        <div className="card space-y-1 !border-gold-500 text-sm">
          {!d.ai_enabled && <p>⚠ The AI professor is off for every learner until an AI key is added. <Link className="text-brand-500 underline" to="/admin/integrations">Add a free Gemini key</Link>.</p>}
          {!d.email_enabled && <p>ℹ Email isn't configured: accounts work without email confirmation, and you send password-reset links from each learner's page. <Link className="text-brand-500 underline" to="/admin/integrations">Set up email</Link>.</p>}
        </div>
      )}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Registered learners" value={d.learners.total} sub={`${d.learners.new_7d} new this week · ${d.learners.new_30d} this month`} />
        <Stat label="Active learners" value={d.learners.active} sub={`${d.learners.inactive} inactive · ${d.learners.suspended} suspended`} />
        <Stat label="Lessons completed" value={d.lessons_completed} sub={`${d.learning_hours} learning hours`} />
        <Stat label="Average performance" value={pct(d.average_performance_30d)} sub="all activities, last 30 days" />
        <Stat label="Placement tests" value={d.placement.taken} sub={`${d.placement.learners_placed} learners placed`} />
        <Stat label="Business English" value={d.business_enrolments} sub="learners with Business Academy activity" />
        <Stat label="Unconfirmed emails" value={d.learners.unverified} />
        <Stat label="Need attention" value={d.attention.length} />
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="card"><h2 className="mb-3 font-semibold">Distribution by CEFR level</h2>
          <div className="space-y-2">{Object.entries(d.cefr_distribution).map(([k, v]) => (
            <Link key={k} to={`/admin/learners?level=${k === "Not placed" ? "none" : k}`} className="flex items-center gap-3 text-sm hover:text-brand-500">
              <span className="w-20 shrink-0">{k}</span><span className="h-3 rounded bg-brand-500" style={{ width: `${(v / maxDist) * 70}%`, minWidth: v ? 6 : 0 }} /><span className="text-ink-400">{v}</span></Link>))}</div></div>
        <div className="card"><h2 className="mb-3 font-semibold">Learners requiring attention</h2>
          {d.attention.length === 0 ? <p className="muted">No one right now.</p> : <ul className="space-y-2 text-sm">{d.attention.slice(0, 10).map((a) => (
            <li key={a.user_id}><Link to={`/admin/learners/${a.user_id}`} className="font-medium hover:text-brand-500">{a.name}</Link> <span className="text-xs text-ink-400">{a.email}</span>
              <div className="text-xs text-amber-600 dark:text-amber-300">{a.reasons.join(" · ")}</div></li>))}</ul>}</div>
      </div>
      <div className="card"><h2 className="mb-3 font-semibold">Recent learning activity</h2>
        {d.recent.length === 0 ? <p className="muted">No activity yet.</p> : (
          <div className="overflow-x-auto"><table className="w-full text-sm"><tbody>{d.recent.map((r, i) => (
            <tr key={i} className="border-t border-ink-100 dark:border-ink-800"><td className="py-1.5"><Link className="hover:text-brand-500" to={`/admin/learners/${r.user_id}`}>{r.learner}</Link></td>
              <td className="capitalize">{r.skill}</td><td className="max-w-[16rem] truncate text-ink-400">{r.item}</td><td>{pct(r.score)}</td><td className="text-ink-400">{dateTime(r.date)}</td></tr>))}</tbody></table></div>)}
      </div>
    </div>
  );
}
