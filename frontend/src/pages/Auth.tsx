import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, ApiError, auth } from "../lib/api";
import { ErrorBox } from "../components/ui";

export interface User {
  id: number; email: string; first_name: string; last_name: string; country: string | null; preferred_language: string;
  objectives: string[]; role: string; status: string; email_verified: boolean; created_at: string; last_login_at: string | null;
  notification_prefs: Record<string, boolean>; permissions: string[]; is_admin: boolean; level: string | null;
}
export interface AuthConfig { mode: string; registration_open: boolean; email_enabled: boolean; verification_required: boolean; setup_available: boolean; platform_name: string }

export const LANGUAGES: [string, string][] = [["fr", "Français"], ["en", "English"], ["es", "Español"], ["pt", "Português"], ["ar", "العربية"], ["zh", "中文"], ["de", "Deutsch"], ["it", "Italiano"], ["other", "Other"]];
export const OBJECTIVES = ["Everyday communication", "Work and career", "Business English", "Finance and banking", "University studies",
  "IELTS / TOEFL / Cambridge exam", "Immigration to Canada", "Travel", "Pronunciation and accent", "Writing"];

function Shell({ title, sub, children }: { title: string; sub?: string; children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen place-items-center p-4">
      <div className="card w-full max-w-lg space-y-4">
        <div className="text-center"><div className="font-serif text-2xl">English Mastery <span className="text-gold-500">AI</span></div>
          <div className="text-xs text-ink-400">Your Personal Intelligent English Academy</div></div>
        <div><h1 className="h1 !text-2xl">{title}</h1>{sub && <p className="muted mt-1">{sub}</p>}</div>
        {children}
      </div>
    </div>
  );
}

function useConfig() {
  const [c, setC] = useState<AuthConfig | null>(null);
  useEffect(() => { api.get<AuthConfig>("/api/auth/config").then(setC).catch(() => {}); }, []);
  return c;
}

function Waking() {
  return <p className="text-center text-xs text-ink-400">Connecting to the academy… The first visit after a quiet period can take up to a minute while the server wakes up.</p>;
}

export function Login({ onSignedIn }: { onSignedIn: (u: User) => void }) {
  const cfg = useConfig();
  const [f, setF] = useState({ email: "", password: "" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [unverified, setUnverified] = useState(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setErr(null); setUnverified(false);
    try {
      const r = await api.post<{ token: string; user: User }>("/api/auth/login", f);
      auth.set(r.token); onSignedIn(r.user);
    } catch (x) {
      const a = x as ApiError; setErr(a.message);
      if (a.status === 403 && a.message.includes("confirm your email")) setUnverified(true);
    } finally { setBusy(false); }
  }
  return (
    <Shell title="Sign in" sub="Welcome back. Your progress is saved to your account and follows you on any device.">
      {!cfg && <Waking />}
      {cfg?.setup_available && <div className="rounded-xl border border-gold-500 p-3 text-sm">First launch: <Link className="font-medium text-brand-500 underline" to="/admin-setup">create the Super Administrator account</Link> with your setup code.</div>}
      <form className="space-y-3" onSubmit={submit}>
        <div><label className="label">Email</label><input className="input" type="email" autoComplete="email" required value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></div>
        <div><label className="label">Password</label><input className="input" type="password" autoComplete="current-password" required value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} /></div>
        <ErrorBox msg={err} />
        {unverified && <ResendVerification email={f.email} />}
        <button className="btn-primary w-full" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
      </form>
      <div className="flex justify-between text-sm"><Link className="text-brand-500" to="/forgot-password">Forgot your password?</Link>
        {cfg?.registration_open !== false && <Link className="text-brand-500" to="/register">Create an account</Link>}</div>
    </Shell>
  );
}

function ResendVerification({ email }: { email: string }) {
  const [sent, setSent] = useState(false);
  return sent ? <p className="text-sm text-emerald-500">If the account exists, a new confirmation email is on its way.</p>
    : <button type="button" className="btn-ghost w-full" onClick={async () => { await api.post("/api/auth/resend-verification", { email }); setSent(true); }}>Send me a new confirmation email</button>;
}

const EMPTY = { first_name: "", last_name: "", email: "", password: "", password_confirm: "", country: "Canada", preferred_language: "fr", objectives: [] as string[], accept_privacy: false };

function RegistrationFields({ f, set }: { f: typeof EMPTY; set: (k: string, v: unknown) => void }) {
  const pwOk = f.password.length >= 10 && /\d/.test(f.password) && /[a-zA-Z]/.test(f.password);
  return (
    <>
      <div className="grid gap-3 sm:grid-cols-2">
        <div><label className="label">First name</label><input className="input" required autoComplete="given-name" value={f.first_name} onChange={(e) => set("first_name", e.target.value)} /></div>
        <div><label className="label">Last name</label><input className="input" required autoComplete="family-name" value={f.last_name} onChange={(e) => set("last_name", e.target.value)} /></div>
      </div>
      <div><label className="label">Email (your sign-in)</label><input className="input" type="email" required autoComplete="email" value={f.email} onChange={(e) => set("email", e.target.value)} /></div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div><label className="label">Password</label><input className="input" type="password" required minLength={10} autoComplete="new-password" value={f.password} onChange={(e) => set("password", e.target.value)} />
          <p className={`mt-1 text-xs ${pwOk ? "text-emerald-500" : "text-ink-400"}`}>At least 10 characters, with letters and a number.</p></div>
        <div><label className="label">Confirm password</label><input className="input" type="password" required autoComplete="new-password" value={f.password_confirm} onChange={(e) => set("password_confirm", e.target.value)} />
          {f.password_confirm && f.password !== f.password_confirm && <p className="mt-1 text-xs text-rose-500">The passwords don't match.</p>}</div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div><label className="label">Country</label><input className="input" required autoComplete="country-name" value={f.country} onChange={(e) => set("country", e.target.value)} /></div>
        <div><label className="label">Preferred language</label><select className="input" value={f.preferred_language} onChange={(e) => set("preferred_language", e.target.value)}>{LANGUAGES.map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></div>
      </div>
      <div><label className="label">Learning objectives</label>
        <div className="flex flex-wrap gap-1.5">{OBJECTIVES.map((o) => {
          const on = f.objectives.includes(o);
          return <button type="button" key={o} className={`pill border ${on ? "border-brand-500 bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-100" : "border-ink-200 dark:border-ink-800"}`}
            onClick={() => set("objectives", on ? f.objectives.filter((x) => x !== o) : [...f.objectives, o])}>{on ? "✓ " : ""}{o}</button>;
        })}</div></div>
    </>
  );
}

export function Register({ onSignedIn }: { onSignedIn: (u: User) => void }) {
  const cfg = useConfig();
  const [f, setF] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [checkEmail, setCheckEmail] = useState<string | null>(null);
  const set = (k: string, v: unknown) => setF((x) => ({ ...x, [k]: v }));
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setErr(null);
    try {
      const r = await api.post<{ verification_required: boolean; token?: string; user?: User; email?: string }>("/api/auth/register", f);
      if (r.verification_required) setCheckEmail(r.email!);
      else { auth.set(r.token!); onSignedIn(r.user!); }
    } catch (x) { setErr((x as Error).message); } finally { setBusy(false); }
  }
  if (checkEmail) return (
    <Shell title="Check your inbox" sub={`We sent a confirmation link to ${checkEmail}. Click it to activate your account, then sign in.`}>
      <ResendVerification email={checkEmail} />
      <Link to="/login" className="btn-primary block text-center">Go to sign in</Link>
    </Shell>
  );
  if (cfg && !cfg.registration_open) return <Shell title="Registration is closed" sub="The academy isn't accepting new learners right now."><Link className="text-brand-500" to="/login">Sign in</Link></Shell>;
  return (
    <Shell title="Create your learner account" sub="Free to join. After sign-up, a placement test finds your level (A1–C2) and opens the right programme.">
      {!cfg && <Waking />}
      <form className="space-y-3" onSubmit={submit}>
        <RegistrationFields f={f} set={set} />
        <label className="flex items-start gap-2 text-xs text-ink-600 dark:text-ink-400"><input type="checkbox" className="mt-0.5" checked={f.accept_privacy} onChange={(e) => set("accept_privacy", e.target.checked)} required />
          <span>I agree that English Mastery AI stores my account details and learning records to run my course and show my progress to the academy's administrators. My data is never sold. I can download or delete it at any time from My Account. (<Link className="underline" to="/privacy">Privacy notice</Link>)</span></label>
        <ErrorBox msg={err} />
        <button className="btn-primary w-full" disabled={busy || f.password !== f.password_confirm}>{busy ? "Creating your account…" : "Create my account"}</button>
      </form>
      <p className="text-center text-sm">Already registered? <Link className="text-brand-500" to="/login">Sign in</Link></p>
    </Shell>
  );
}

export function AdminSetup({ onSignedIn }: { onSignedIn: (u: User) => void }) {
  const [f, setF] = useState({ ...EMPTY, setup_code: "", accept_privacy: true });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: string, v: unknown) => setF((x) => ({ ...x, [k]: v }));
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setErr(null);
    try { const r = await api.post<{ token: string; user: User }>("/api/auth/setup-admin", f); auth.set(r.token); onSignedIn(r.user); }
    catch (x) { setErr((x as Error).message); } finally { setBusy(false); }
  }
  return (
    <Shell title="Create the Super Administrator" sub="One-time setup. Use the setup code you were given; it stops working once this account exists.">
      <form className="space-y-3" onSubmit={submit}>
        <div><label className="label">Setup code</label><input className="input font-mono" required value={f.setup_code} onChange={(e) => set("setup_code", e.target.value)} /></div>
        <RegistrationFields f={f} set={set} />
        <ErrorBox msg={err} />
        <button className="btn-primary w-full" disabled={busy}>{busy ? "Creating…" : "Create Super Administrator"}</button>
      </form>
    </Shell>
  );
}

export function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [done, setDone] = useState<{ email_enabled: boolean } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  return (
    <Shell title="Reset your password" sub="Enter the email address of your account.">
      {done ? (
        done.email_enabled ? <p className="text-sm">If an account exists for <b>{email}</b>, a reset link is on its way. It's valid for 2 hours.</p>
          : <p className="text-sm">Password-reset emails aren't switched on yet. Please contact the academy: an administrator will send you a secure, single-use reset link.</p>
      ) : (
        <form className="space-y-3" onSubmit={async (e) => { e.preventDefault(); setErr(null); try { setDone(await api.post("/api/auth/forgot-password", { email })); } catch (x) { setErr((x as Error).message); } }}>
          <input className="input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
          <ErrorBox msg={err} />
          <button className="btn-primary w-full">Send reset link</button>
        </form>
      )}
      <Link className="text-sm text-brand-500" to="/login">← Back to sign in</Link>
    </Shell>
  );
}

export function ResetPassword() {
  const [params] = useSearchParams();
  const nav = useNavigate();
  const [f, setF] = useState({ password: "", password_confirm: "" });
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState(false);
  return (
    <Shell title="Choose a new password" sub="At least 10 characters, with letters and a number. You'll be signed out of other devices.">
      {ok ? <><p className="text-sm text-emerald-500">Your password has been changed.</p><button className="btn-primary w-full" onClick={() => { auth.set(null); nav("/login"); window.location.reload(); }}>Sign in</button></> : (
        <form className="space-y-3" onSubmit={async (e) => { e.preventDefault(); setErr(null); try { await api.post("/api/auth/reset-password", { ...f, token: params.get("token") ?? "" }); setOk(true); } catch (x) { setErr((x as Error).message); } }}>
          <input className="input" type="password" autoComplete="new-password" placeholder="New password" required value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} />
          <input className="input" type="password" autoComplete="new-password" placeholder="Confirm new password" required value={f.password_confirm} onChange={(e) => setF({ ...f, password_confirm: e.target.value })} />
          <ErrorBox msg={err} />
          <button className="btn-primary w-full">Save new password</button>
        </form>
      )}
    </Shell>
  );
}

export function VerifyEmail() {
  const [params] = useSearchParams();
  const [state, setState] = useState<"working" | "ok" | string>("working");
  useEffect(() => { api.post("/api/auth/verify-email", { token: params.get("token") ?? "" }).then(() => setState("ok")).catch((e) => setState(e.message)); }, []); // eslint-disable-line
  return (
    <Shell title="Email confirmation">
      {state === "working" ? <p className="muted">Confirming…</p> : state === "ok" ? <p className="text-emerald-500">Your email address is confirmed. You can sign in now.</p> : <ErrorBox msg={state} />}
      <Link to="/" className="btn-primary block text-center">Continue</Link>
    </Shell>
  );
}

export function Privacy() {
  return (
    <div className="mx-auto max-w-3xl space-y-4 p-6 leading-relaxed">
      <h1 className="h1">Privacy notice</h1>
      <p>English Mastery AI collects your name, email address, country, preferred language and learning objectives to create your account, plus your learning records (answers, scores, conversations, writing, study time) to run your course and show your progress.</p>
      <p><b>Who can see it.</b> You, and the academy's authorised administrators for teaching and support. Every administrative action on learner accounts is recorded in an audit log. Your data is never sold.</p>
      <p><b>AI services.</b> When you use the AI professor (conversation, writing correction, speaking assessment), the text of that exercise is sent to the AI provider configured by the academy (for example Google Gemini) to produce the feedback. Speech recognition uses your browser's built-in service.</p>
      <p><b>Security.</b> Passwords are stored only as salted scrypt hashes; connections use HTTPS; sign-in sessions expire and can be revoked; API keys are encrypted on the server and never sent to browsers.</p>
      <p><b>Your rights (Canada — PIPEDA and provincial laws, including Québec's Law 25).</b> From <i>My Account</i> you can view and correct your information, download your progress report and a full export of your data, and permanently delete your account. For any other request, contact the academy administrator.</p>
      <Link to="/" className="text-brand-500">← Back</Link>
    </div>
  );
}
