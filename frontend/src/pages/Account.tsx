import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, auth } from "../lib/api";
import { ErrorBox } from "../components/ui";
import { LANGUAGES, OBJECTIVES, User } from "./Auth";
import { LEVEL_NAMES } from "./Academy";

export default function Account({ user, onUser }: { user: User; onUser: (u: User | null) => void }) {
  const [f, setF] = useState({ first_name: user.first_name, last_name: user.last_name, country: user.country ?? "", preferred_language: user.preferred_language,
    objectives: user.objectives, notification_prefs: user.notification_prefs });
  const [pw, setPw] = useState({ current_password: "", password: "", password_confirm: "" });
  const [del, setDel] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const ok = (m: string) => { setErr(null); setMsg(m); setTimeout(() => setMsg(null), 3000); };
  const fail = (e: unknown) => { setMsg(null); setErr((e as Error).message); };
  useEffect(() => { window.scrollTo(0, 0); }, []);

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div><h1 className="h1">My account</h1><p className="muted mt-1">Your personal information, password, notifications and data.</p></div>
      {msg && <div className="rounded-xl bg-emerald-50 p-3 text-sm text-emerald-800 dark:bg-emerald-500/10 dark:text-emerald-300">{msg}</div>}
      <ErrorBox msg={err} />

      <section className="card grid gap-3 sm:grid-cols-3">
        <div><div className="label">Email (sign-in)</div><div className="font-medium break-all">{user.email}</div><div className={`text-xs ${user.email_verified ? "text-emerald-500" : "text-ink-400"}`}>{user.email_verified ? "✓ confirmed" : "not confirmed yet"}</div></div>
        <div><div className="label">Current English level</div><div className="font-serif text-2xl">{user.level ? `${user.level} — ${LEVEL_NAMES[user.level]}` : "Not placed yet"}</div>
          <Link to={user.level ? `/level/${user.level}` : "/tests?start=placement"} className="text-xs text-brand-500">{user.level ? "Open my programme →" : "Take the placement test →"}</Link></div>
        <div><div className="label">Member since</div><div>{new Date(user.created_at).toLocaleDateString()}</div><Link to="/history" className="text-xs text-brand-500">My learning history →</Link></div>
      </section>

      <section className="card space-y-3">
        <h2 className="font-semibold">Personal information</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <div><label className="label">First name</label><input className="input" value={f.first_name} onChange={(e) => setF({ ...f, first_name: e.target.value })} /></div>
          <div><label className="label">Last name</label><input className="input" value={f.last_name} onChange={(e) => setF({ ...f, last_name: e.target.value })} /></div>
          <div><label className="label">Country</label><input className="input" value={f.country} onChange={(e) => setF({ ...f, country: e.target.value })} /></div>
          <div><label className="label">Preferred language</label><select className="input" value={f.preferred_language} onChange={(e) => setF({ ...f, preferred_language: e.target.value })}>{LANGUAGES.map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></div>
        </div>
        <div><label className="label">Learning objectives</label><div className="flex flex-wrap gap-1.5">{OBJECTIVES.map((o) => {
          const on = f.objectives.includes(o);
          return <button type="button" key={o} className={`pill border ${on ? "border-brand-500 bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-100" : "border-ink-200 dark:border-ink-800"}`}
            onClick={() => setF({ ...f, objectives: on ? f.objectives.filter((x) => x !== o) : [...f.objectives, o] })}>{on ? "✓ " : ""}{o}</button>;
        })}</div></div>
        <div><label className="label">Notifications</label>
          {([["email", "Email me important messages (assessment results, password changes)"], ["milestones", "Celebrate milestones in the app"], ["reminders", "Study reminders"]] as const).map(([k, l]) => (
            <label key={k} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.notification_prefs[k] !== false} onChange={(e) => setF({ ...f, notification_prefs: { ...f.notification_prefs, [k]: e.target.checked } })} />{l}</label>))}
          <p className="mt-1 text-xs text-ink-400">The daily reminder time is in <Link className="underline" to="/settings">Settings</Link>.</p></div>
        <div className="flex justify-end"><button className="btn-primary" onClick={async () => { try { onUser(await api.put<User>("/api/auth/me", f)); ok("Saved successfully."); } catch (e) { fail(e); } }}>Save changes</button></div>
      </section>

      <section className="card space-y-3">
        <h2 className="font-semibold">Change password</h2>
        <div className="grid gap-3 sm:grid-cols-3">
          <input className="input" type="password" autoComplete="current-password" placeholder="Current password" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} />
          <input className="input" type="password" autoComplete="new-password" placeholder="New password" value={pw.password} onChange={(e) => setPw({ ...pw, password: e.target.value })} />
          <input className="input" type="password" autoComplete="new-password" placeholder="Confirm new password" value={pw.password_confirm} onChange={(e) => setPw({ ...pw, password_confirm: e.target.value })} />
        </div>
        <div className="flex flex-wrap justify-between gap-2"><p className="text-xs text-ink-400">At least 10 characters with letters and a number. Other devices will be signed out.</p>
          <button className="btn-primary" disabled={!pw.current_password || !pw.password} onClick={async () => { try { await api.post("/api/auth/change-password", pw); setPw({ current_password: "", password: "", password_confirm: "" }); ok("Password changed."); } catch (e) { fail(e); } }}>Change password</button></div>
      </section>

      <section className="card space-y-3">
        <h2 className="font-semibold">Reports and your data</h2>
        <div className="flex flex-wrap gap-2">
          <button className="btn-ghost" onClick={() => api.download("/api/auth/me/report.pdf", "my-progress-report.pdf").catch(fail)}>⬇ Download my progress report (PDF)</button>
          <button className="btn-ghost" onClick={() => api.download("/api/auth/me/export.json", "my-english-mastery-data.json").catch(fail)}>⬇ Download all my data (JSON)</button>
          <button className="btn-ghost" onClick={async () => { await api.post("/api/auth/logout-all"); auth.set(null); onUser(null); }}>Sign out on every device</button>
          <Link className="btn-ghost" to="/privacy">Privacy notice</Link>
        </div>
      </section>

      {user.role !== "super_admin" && (
        <section className="card space-y-3 !border-rose-500/40">
          <h2 className="font-semibold text-rose-500">Delete my account</h2>
          <p className="text-sm">This permanently deletes your account and every learning record (lessons, tests, conversations, writing). It can't be undone.</p>
          <div className="flex flex-wrap gap-2"><input className="input sm:!w-72" type="password" placeholder="Your password to confirm" value={del} onChange={(e) => setDel(e.target.value)} />
            <button className="btn-primary !bg-rose-600" disabled={!del} onClick={async () => {
              if (!window.confirm("Permanently delete your account and all your learning records?")) return;
              try { await api.post("/api/auth/me/delete", { password: del }); auth.set(null); onUser(null); } catch (e) { fail(e); }
            }}>Delete permanently</button></div>
        </section>
      )}
    </div>
  );
}
