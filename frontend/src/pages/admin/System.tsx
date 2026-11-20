import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../lib/api";
import { ErrorBox } from "../../components/ui";
import SelfTest from "../../components/SelfTest";
import type { User } from "../Auth";
import { date, dateTime } from "./AdminApp";

function Flash({ msg }: { msg: string | null }) {
  return msg ? <div className="rounded-xl bg-emerald-50 p-3 text-sm text-emerald-800 dark:bg-emerald-500/10 dark:text-emerald-300">{msg}</div> : null;
}

// ------------------------------------------------------------------ platform settings
interface S { platform_name: string; registration_open: boolean; require_email_verification: boolean | string; session_days: number; lockout_after_failed_logins: number; inactive_after_days: number; notifications: Record<string, boolean>; level_test_pass_mark: number }
const NOTE_LABELS: Record<string, string> = {
  learner_welcome: "Learners: welcome message", learner_assessment: "Learners: assessment results", learner_milestone: "Learners: milestones", learner_reminders: "Learners: study reminders",
  admin_new_registration: "Admins: new registrations", admin_assessment: "Admins: assessment completions", admin_inactive: "Admins: inactive learners", admin_security: "Admins: unusual account activity (lockouts)", admin_errors: "Admins: important technical errors",
};

export function PlatformSettings() {
  const [s, setS] = useState<S | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => { api.get<S>("/api/admin/settings").then(setS).catch((e) => setErr(e.message)); }, []);
  if (!s) return err ? <ErrorBox msg={err} /> : <div className="text-ink-400">Loading…</div>;
  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <h1 className="h1">Platform settings</h1>
      <Flash msg={msg} /><ErrorBox msg={err} />
      <div className="card grid gap-3 sm:grid-cols-2">
        <div><label className="label">Academy name</label><input className="input" value={s.platform_name} onChange={(e) => setS({ ...s, platform_name: e.target.value })} /></div>
        <label className="flex items-center gap-2 self-end pb-2 text-sm"><input type="checkbox" checked={s.registration_open} onChange={(e) => setS({ ...s, registration_open: e.target.checked })} /> New learners can register</label>
        <div><label className="label">Email confirmation before first sign-in</label><select className="input" value={String(s.require_email_verification)} onChange={(e) => setS({ ...s, require_email_verification: e.target.value === "auto" ? "auto" : e.target.value === "true" })}>
          <option value="auto">Automatic: required once email is set up</option><option value="true">Always required</option><option value="false">Never required</option></select></div>
        <div><label className="label">Sign-in session length (days)</label><input type="number" min={1} max={90} className="input" value={s.session_days} onChange={(e) => setS({ ...s, session_days: +e.target.value })} /></div>
        <div><label className="label">Lock an account after N failed sign-ins (15 min)</label><input type="number" min={3} max={20} className="input" value={s.lockout_after_failed_logins} onChange={(e) => setS({ ...s, lockout_after_failed_logins: +e.target.value })} /></div>
        <div><label className="label">A learner counts as inactive after (days)</label><input type="number" min={3} max={120} className="input" value={s.inactive_after_days} onChange={(e) => setS({ ...s, inactive_after_days: +e.target.value })} /></div>
      </div>
      <div className="card space-y-1"><h2 className="mb-2 font-semibold">Notifications</h2>
        {Object.entries(s.notifications).map(([k, v]) => <label key={k} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={v} onChange={(e) => setS({ ...s, notifications: { ...s.notifications, [k]: e.target.checked } })} />{NOTE_LABELS[k] ?? k}</label>)}
        <p className="pt-2 text-xs text-ink-400">Emails are sent only when an email service is configured (AI, email & status). In-app notifications always work. Level test pass marks are set in Placement test.</p>
      </div>
      <div className="flex justify-end"><button className="btn-primary" onClick={async () => { try { setS(await api.put<S>("/api/admin/settings", s)); setMsg("Saved successfully."); setErr(null); } catch (e) { setErr((e as Error).message); } }}>Save settings</button></div>
    </div>
  );
}

// ------------------------------------------------------------------ integrations & status
interface Status {
  database: { engine: string; host: string; latency_ms: number; size_bytes: number | null; users: number }; storage: { media_bytes: number; media_files: number; limit_note: string };
  ai: { provider: string; model: string; keys: Record<string, boolean> }; email: { provider: string | null; from: string | null; brevo_key: boolean; outbox: Record<string, number> };
  payments: { stripe_key: boolean; paypal_key: boolean; active: boolean }; security: Record<string, unknown>; mode: string; server_time: string;
}
const MODELS: Record<string, string> = { gemini: "gemini-2.5-flash", openai: "gpt-4o-mini", anthropic: "claude-sonnet-5-5" };

export function Integrations() {
  const [st, setSt] = useState<Status | null>(null);
  const [key, setKey] = useState({ provider: "gemini", api_key: "" });
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const load = () => api.get<Status>("/api/admin/status").then(setSt).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);
  async function saveKey() {
    setErr(null);
    try {
      await api.post("/api/system/keys", { ...key, api_key: key.api_key.trim() });
      if (MODELS[key.provider]) await api.put("/api/system/providers", { llm_provider: key.provider, llm_model: MODELS[key.provider], azure_speech_region: "" });
      setKey({ ...key, api_key: "" }); setMsg("Key saved (encrypted). Run the live tests below to confirm it works."); load();
    } catch (e) { setErr((e as Error).message); }
  }
  if (!st) return err ? <ErrorBox msg={err} /> : <div className="text-ink-400">Loading…</div>;
  const mb = (b: number | null) => (b == null ? "—" : `${(b / 1048576).toFixed(1)} MB`);
  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <h1 className="h1">AI, email & system status</h1>
      <Flash msg={msg} /><ErrorBox msg={err} />
      <div className="grid gap-4 md:grid-cols-3">
        <div className="card text-sm"><div className="label">Database</div><div className="font-medium">{st.database.engine} · {st.database.host}</div><div className="text-ink-400">{st.database.latency_ms} ms · {mb(st.database.size_bytes)} · {st.database.users} accounts</div></div>
        <div className="card text-sm"><div className="label">Storage</div><div className="font-medium">{st.storage.media_files} media files · {mb(st.storage.media_bytes)}</div><div className="text-ink-400">{st.storage.limit_note}</div></div>
        <div className="card text-sm"><div className="label">Security</div><div className="text-ink-400">HTTPS · scrypt password hashing · rate limiting · {String(st.security.session_days)}-day sessions · secret key {st.security.secret_key_set ? "set" : "MISSING"}</div></div>
      </div>
      <div className="card space-y-3">
        <h2 className="font-semibold">API keys (encrypted on the server, never sent to browsers)</h2>
        <div className="flex flex-wrap gap-3 text-sm">{Object.entries({ ...st.ai.keys, brevo: st.email.brevo_key, stripe: st.payments.stripe_key }).map(([k, v]) => <span key={k} className={v ? "text-emerald-500" : "text-ink-400"}>{v ? "●" : "○"} {k}</span>)}</div>
        <div className="grid gap-2 sm:grid-cols-[200px_1fr_auto]">
          <select className="input" value={key.provider} onChange={(e) => setKey({ ...key, provider: e.target.value })}>
            <option value="gemini">Google Gemini (free tier) — AI professor</option><option value="openai">OpenAI — AI professor + natural voices</option><option value="anthropic">Anthropic — AI professor</option>
            <option value="azure_speech">Azure Speech — phoneme scoring</option><option value="brevo">Brevo — email (free 300/day)</option><option value="stripe">Stripe — payments (stored only, not active)</option></select>
          <input className="input" type="password" placeholder="Paste the key" value={key.api_key} onChange={(e) => setKey({ ...key, api_key: e.target.value })} />
          <button className="btn-primary" disabled={key.api_key.trim().length < 10} onClick={saveKey}>Save key</button>
        </div>
        <p className="text-xs text-ink-400">AI professor in use: <b>{st.ai.provider}</b> ({st.ai.model}). Free Gemini key: <a className="text-brand-500 underline" href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer">aistudio.google.com/apikey</a>. Email sender: {st.email.from ?? "not set (EMA_MAIL_FROM)"} · provider {st.email.provider ?? "not configured"} · outbox {JSON.stringify(st.email.outbox)}.</p>
      </div>
      <SelfTest />
      <div className="card text-sm"><h2 className="mb-1 font-semibold">Backups</h2>
        <p className="text-ink-400">The database provider keeps automatic point-in-time history. You can also download a full JSON export (passwords and keys excluded).</p>
        <button className="btn-ghost mt-2" onClick={() => api.download("/api/admin/backup", `english-mastery-backup-${new Date().toISOString().slice(0, 10)}.json`).catch((e) => setErr(e.message))}>⬇ Download a backup now</button></div>
    </div>
  );
}

// ------------------------------------------------------------------ roles & staff
interface Role { name: string; label: string; description: string; active: boolean; permissions: string[]; users: number }
export function RolesAndStaff({ me }: { me: User }) {
  const [r, setR] = useState<{ roles: Role[]; permissions: Record<string, string> } | null>(null);
  const [staff, setStaff] = useState<{ user_id: number; name: string; email: string; role: string; last_login: string | null }[]>([]);
  const [inv, setInv] = useState({ email: "", first_name: "", last_name: "", role: "admin" });
  const [link, setLink] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const load = () => { api.get<typeof r>("/api/admin/roles").then(setR).catch((e) => setErr(e.message)); api.get<{ items: typeof staff }>("/api/admin/learners?role=staff&size=100").then((x) => setStaff(x.items)).catch(() => {}); };
  useEffect(() => { load(); }, []);
  const canEdit = me.role === "super_admin" || me.permissions.includes("users.roles");
  if (!r) return err ? <ErrorBox msg={err} /> : <div className="text-ink-400">Loading…</div>;
  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <h1 className="h1">Administrators & roles</h1>
      <Flash msg={msg} /><ErrorBox msg={err} />
      <div className="card overflow-x-auto"><h2 className="mb-2 font-semibold">Role permissions</h2>
        <table className="w-full min-w-[720px] text-sm"><thead><tr><th className="py-2 text-left">Permission</th>{r.roles.map((x) => <th key={x.name} className="px-2 text-center">{x.label}<div className="text-[10px] font-normal text-ink-400">{x.users} user(s){x.active ? "" : " · inactive role"}</div></th>)}</tr></thead>
          <tbody>{Object.entries(r.permissions).map(([code, desc]) => (
            <tr key={code} className="border-t border-ink-100 dark:border-ink-800"><td className="py-1.5">{desc}<div className="text-[10px] text-ink-400">{code}</div></td>
              {r.roles.map((x) => <td key={x.name} className="text-center"><input type="checkbox" disabled={!canEdit || x.name === "super_admin" || x.name === "learner"} checked={x.permissions.includes(code)}
                onChange={async (e) => { const perms = e.target.checked ? [...x.permissions, code] : x.permissions.filter((p) => p !== code); try { await api.put(`/api/admin/roles/${x.name}`, { permissions: perms }); setMsg("Permissions updated."); load(); } catch (er) { setErr((er as Error).message); } }} /></td>)}</tr>))}</tbody></table>
        <p className="mt-2 text-xs text-ink-400">The Super Administrator always holds every permission. The Teacher role is prepared for the future teacher portal and can't sign in to this portal yet.</p></div>
      <div className="card"><h2 className="mb-2 font-semibold">Administrators</h2>
        <table className="w-full text-sm"><tbody>{staff.map((s) => <tr key={s.user_id} className="border-t border-ink-100 dark:border-ink-800"><td className="py-1.5"><Link className="hover:text-brand-500" to={`/admin/learners/${s.user_id}`}>{s.name}</Link></td><td className="text-ink-400">{s.email}</td><td>{s.role.replace("_", " ")}</td><td className="text-ink-400">last login {date(s.last_login)}</td></tr>)}</tbody></table>
        {canEdit && <div className="mt-3 grid gap-2 sm:grid-cols-5">
          <input className="input sm:col-span-2" type="email" placeholder="Email" value={inv.email} onChange={(e) => setInv({ ...inv, email: e.target.value })} />
          <input className="input" placeholder="First name" value={inv.first_name} onChange={(e) => setInv({ ...inv, first_name: e.target.value })} />
          <input className="input" placeholder="Last name" value={inv.last_name} onChange={(e) => setInv({ ...inv, last_name: e.target.value })} />
          <div className="flex gap-2"><select className="input" value={inv.role} onChange={(e) => setInv({ ...inv, role: e.target.value })}><option value="admin">Administrator</option>{me.role === "super_admin" && <option value="super_admin">Super admin</option>}</select>
            <button className="btn-primary" onClick={async () => { setErr(null); try { const x = await api.post<{ link: string; emailed: boolean }>("/api/admin/staff", inv); setLink(x.emailed ? null : x.link); setMsg(x.emailed ? "Invitation emailed." : "Account created. Send the activation link below to the new administrator."); load(); } catch (e) { setErr((e as Error).message); } }}>Invite</button></div>
        </div>}
        {link && <div className="mt-2 flex gap-2"><input className="input font-mono text-xs" readOnly value={link} onFocus={(e) => e.target.select()} /><button className="btn-ghost" onClick={() => navigator.clipboard?.writeText(link)}>Copy</button></div>}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ audit
export function AuditLog() {
  const [rows, setRows] = useState<{ id: number; date: string; actor: string | null; action: string; target: string; details: unknown; ip: string | null }[]>([]);
  const [action, setAction] = useState("");
  const [page, setPage] = useState(1);
  useEffect(() => { api.get<typeof rows>(`/api/admin/audit?action=${action}&page=${page}`).then(setRows); }, [action, page]);
  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <h1 className="h1">Audit log</h1>
      <select className="input !w-64" value={action} onChange={(e) => { setAction(e.target.value); setPage(1); }}>
        <option value="">All actions</option>{["auth.", "learner.", "content.", "placement.", "settings.", "secrets.", "roles.", "staff.", "report.", "backup.", "plans."].map((a) => <option key={a} value={a}>{a.replace(".", "")}</option>)}</select>
      <div className="card overflow-x-auto !p-0"><table className="w-full min-w-[760px] text-sm">
        <thead className="text-left text-xs uppercase text-ink-400"><tr>{["When", "Who", "Action", "Target", "Details", "IP"].map((h) => <th key={h} className="px-4 py-3">{h}</th>)}</tr></thead>
        <tbody>{rows.map((r) => <tr key={r.id} className="border-t border-ink-100 dark:border-ink-800"><td className="whitespace-nowrap px-4 py-1.5">{dateTime(r.date)}</td><td>{r.actor ?? "—"}</td><td className="font-mono text-xs">{r.action}</td><td className="text-xs">{r.target}</td>
          <td className="max-w-xs truncate text-xs text-ink-400">{r.details ? JSON.stringify(r.details) : ""}</td><td className="text-xs text-ink-400">{r.ip}</td></tr>)}</tbody></table></div>
      <div className="flex justify-center gap-2"><button className="btn-ghost" disabled={page === 1} onClick={() => setPage(page - 1)}>← Newer</button><button className="btn-ghost" disabled={rows.length < 100} onClick={() => setPage(page + 1)}>Older →</button></div>
    </div>
  );
}

// ------------------------------------------------------------------ commercial & expansion
interface Plan { id: number; code: string; name: string; description: string; price_monthly_cents: number | null; price_annual_cents: number | null; currency: string; trial_days: number; features: string[]; limits: Record<string, unknown>; for_organizations: boolean; active: boolean }
export function Commercial() {
  const [plans, setPlans] = useState<{ status: string; plans: Plan[] } | null>(null);
  const [com, setCom] = useState<Record<string, unknown> | null>(null);
  const [ex, setEx] = useState<{ features: Record<string, string>; records: Record<string, number> } | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const load = () => { api.get<typeof plans>("/api/admin/plans").then(setPlans); api.get<typeof com>("/api/admin/commerce").then(setCom); api.get<typeof ex>("/api/admin/expansion").then(setEx); };
  useEffect(() => { load(); }, []);
  const money = (c: number | null) => (c == null ? "on quote" : `${(c / 100).toFixed(2)}`);
  const STATUS: Record<string, [string, string]> = { operational: ["Operational", "text-emerald-500"], configured_inactive: ["Configured, not activated", "text-amber-500"], future: ["Architecture ready (future module)", "text-ink-400"] };
  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div><h1 className="h1">Plans, payments & expansion</h1><p className="muted mt-1">Foundations for running English Mastery AI as a business. Nothing here charges anyone: payments stay off until a provider account is connected and you decide to switch them on.</p></div>
      <Flash msg={msg} /><ErrorBox msg={err} />
      {ex && <div className="card"><h2 className="mb-2 font-semibold">Module status</h2>
        <table className="w-full text-sm"><tbody>{[["Learner academy (A1–C2, Business, placement, AI professor)", "operational"], ["Administrator portal", "operational"],
          ["Subscription plans", ex.features.subscriptions], ["Online payments (Stripe / PayPal)", ex.features.payments], ["Teacher portal", ex.features.teacher_portal],
          ["Classes", ex.features.classes], ["Learner groups", ex.features.groups], ["Organisations / corporate training", ex.features.organizations]].map(([n, s]) => (
          <tr key={n} className="border-t border-ink-100 dark:border-ink-800"><td className="py-1.5">{n}</td><td className={STATUS[s]?.[1]}>{STATUS[s]?.[0] ?? s}</td></tr>))}</tbody></table>
        <p className="mt-2 text-xs text-ink-400">Database records today: {Object.entries(ex.records).map(([k, v]) => `${k} ${v}`).join(" · ")}. See docs/ROADMAP.md for the activation plan.</p></div>}
      {com && <div className="card grid gap-2 text-sm sm:grid-cols-3"><h2 className="font-semibold sm:col-span-3">Revenue (from payment records)</h2>
        <div>Total revenue: <b>{money(com.total_revenue_cents as number)}</b></div><div>Active subscriptions: <b>{String(com.active_subscriptions)}</b></div><div>Cancelled: <b>{String(com.cancelled_subscriptions)}</b></div>
        <div>Pending payments: <b>{String(com.pending_payments)}</b></div><div>Failed transactions: <b>{String(com.failed_transactions)}</b></div><div>Invoices: <b>{String(com.invoices)}</b></div>
        <p className="text-xs text-ink-400 sm:col-span-3">{String(com.note)}</p></div>}
      {plans && <div className="card space-y-3"><h2 className="font-semibold">Subscription plans (draft — prices, features, limits and billing periods are configurable)</h2>
        {plans.plans.map((p, i) => (
          <div key={p.code} className="grid gap-2 border-t border-ink-100 pt-3 text-sm first:border-0 first:pt-0 dark:border-ink-800 md:grid-cols-6">
            <input className="input" value={p.name} onChange={(e) => setPlans({ ...plans, plans: plans.plans.map((x, k) => (k === i ? { ...x, name: e.target.value } : x)) })} />
            <input className="input md:col-span-2" value={p.description} onChange={(e) => setPlans({ ...plans, plans: plans.plans.map((x, k) => (k === i ? { ...x, description: e.target.value } : x)) })} />
            <label className="text-xs">Monthly ({p.currency}, cents)<input className="input" type="number" value={p.price_monthly_cents ?? ""} onChange={(e) => setPlans({ ...plans, plans: plans.plans.map((x, k) => (k === i ? { ...x, price_monthly_cents: e.target.value === "" ? null : +e.target.value } : x)) })} /></label>
            <label className="text-xs">Annual (cents)<input className="input" type="number" value={p.price_annual_cents ?? ""} onChange={(e) => setPlans({ ...plans, plans: plans.plans.map((x, k) => (k === i ? { ...x, price_annual_cents: e.target.value === "" ? null : +e.target.value } : x)) })} /></label>
            <div className="flex items-end gap-2"><label className="text-xs">Trial days<input className="input" type="number" value={p.trial_days} onChange={(e) => setPlans({ ...plans, plans: plans.plans.map((x, k) => (k === i ? { ...x, trial_days: +e.target.value } : x)) })} /></label>
              <button className="btn-ghost" onClick={async () => { try { const { id: _id, ...body } = plans.plans[i]; void _id; await api.put(`/api/admin/plans/${p.code}`, body); setMsg(`${p.name} saved.`); } catch (e) { setErr((e as Error).message); } }}>Save</button></div>
            <div className="text-xs text-ink-400 md:col-span-6">Features: {p.features.join(", ")}{Object.keys(p.limits).length ? ` · limits ${JSON.stringify(p.limits)}` : ""}{p.for_organizations ? " · for organisations" : ""}</div>
          </div>))}</div>}
    </div>
  );
}
