import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../lib/api";
import { useAcademy, useProfile } from "../App";
import { ErrorBox, LevelPill } from "../components/ui";

export interface Item {
  key: string; kind: string; ref: string; title: string; route: string | null; available: boolean;
  done: boolean; score: number | null; detail: string; summary?: string;
}
interface TestInfo { attempts: number; best: number; passed: boolean; last_at: string | null }
export interface LevelSummary {
  code: string; name: string; full_name: string; description: string; lesson_count: number; coming_soon: number;
  done: number; percent: number; status: "current" | "completed" | "locked" | "available"; test: TestInfo | null;
  next: { title: string; route: string } | null;
}
interface LevelDetail extends LevelSummary { units: { title: string; items: Item[] }[]; pass_mark: number; next_level: string | null; can_take_test: boolean }
export interface Overview {
  level_confirmed: boolean; current_level: string | null; current_level_name: string | null; levels: LevelSummary[];
  business: { categories: number; lesson_count: number; done: number; percent: number; test: TestInfo | null };
  placement: { done: boolean; date: string | null; last: { level: string; date: string; details: { skills: Record<string, string>; scores: Record<string, number> } } | null };
  next: { title: string; route: string } | null;
}

export const LEVEL_NAMES: Record<string, string> = { A1: "Beginner", A2: "Elementary", B1: "Intermediate", B2: "Upper Intermediate", C1: "Advanced", C2: "Proficiency" };
export const LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"];
const ICON: Record<string, string> = { lesson: "📘", reading: "📰", listening: "🎧", vocab: "🗂️", conversation: "🎙", writing: "✍️", pronunciation: "🗣️", soon: "⏳" };
const KIND: Record<string, string> = { lesson: "Lesson", reading: "Reading", listening: "Listening", vocab: "Vocabulary", conversation: "AI conversation", writing: "Writing", pronunciation: "Pronunciation", soon: "Coming soon" };
const STATUS_LABEL: Record<string, string> = { current: "In progress", completed: "Completed", locked: "Locked", available: "Open" };
const STATUS_CLASS: Record<string, string> = {
  current: "bg-brand-600 text-white", completed: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300",
  locked: "bg-ink-100 text-ink-600 dark:bg-ink-800 dark:text-ink-400", available: "bg-gold-400/20 text-ink-800 dark:text-ink-100",
};
const fmtDate = (s: string | null) => (s ? new Date(s + (s.endsWith("Z") ? "" : "Z")).toLocaleDateString() : "");

export function StatusPill({ s }: { s: string }) {
  return <span className={`pill ${STATUS_CLASS[s]}`}>{s === "locked" ? "🔒 " : s === "completed" ? "✓ " : ""}{STATUS_LABEL[s]}</span>;
}

function Progress({ pct }: { pct: number }) {
  return <div className="h-1.5 rounded-full bg-ink-100 dark:bg-ink-800"><div className="h-1.5 rounded-full bg-brand-500" style={{ width: `${pct}%` }} /></div>;
}

// ------------------------------------------------------------------ dashboard areas
export function AcademyAreas() {
  const { overview: o } = useAcademy();
  if (!o) return <div className="text-ink-400">Loading your academy…</div>;
  return (
    <div className="space-y-6">
      {!o.level_confirmed && <FindYourLevel />}
      <section>
        <div className="mb-3 flex items-end justify-between"><h2 className="font-serif text-2xl">English levels</h2>
          {o.current_level && <span className="text-sm text-ink-400">Your level: <b className="text-ink-800 dark:text-ink-100">{o.current_level} — {o.current_level_name}</b></span>}</div>
        <div className="grid grid-cols-3 gap-4">{o.levels.map((lv) => <LevelCard key={lv.code} lv={lv} />)}</div>
      </section>
      <div className="grid grid-cols-2 gap-4">
        <BusinessCard o={o} />
        <PlacementCard o={o} />
      </div>
    </div>
  );
}

function LevelCard({ lv }: { lv: LevelSummary }) {
  const locked = lv.status === "locked";
  return (
    <Link to={`/level/${lv.code}`} className={`card flex flex-col gap-2 transition hover:border-brand-400 ${lv.status === "current" ? "!border-brand-500" : ""} ${locked ? "opacity-75" : ""}`}>
      <div className="flex items-center justify-between"><span className="font-serif text-3xl">{lv.code}</span><StatusPill s={lv.status} /></div>
      <div className="font-medium">{lv.name}</div>
      <p className="muted line-clamp-2 text-sm">{lv.description}</p>
      <div className="mt-auto space-y-1.5 pt-2">
        <div className="flex justify-between text-xs text-ink-400"><span>{lv.lesson_count} activities{lv.coming_soon ? ` · ${lv.coming_soon} coming soon` : ""}</span><span>{lv.percent}% complete</span></div>
        <Progress pct={lv.percent} />
        <div className="text-xs font-medium text-brand-600 dark:text-brand-100">{locked ? "View syllabus →" : lv.status === "completed" ? "Review this level →" : "Open level →"}</div>
      </div>
    </Link>
  );
}

function BusinessCard({ o }: { o: Overview }) {
  return (
    <Link to="/business" className="card flex flex-col gap-2 transition hover:border-brand-400">
      <div className="flex items-center justify-between"><span className="text-3xl">💼</span><span className="pill bg-gold-400/20">Separate programme · B1+</span></div>
      <div className="font-serif text-2xl">Business English Academy</div>
      <p className="muted text-sm">{o.business.categories} professional categories, from meetings and negotiation to corporate finance and executive communication, with AI simulations.</p>
      <div className="mt-auto space-y-1.5 pt-2">
        <div className="flex justify-between text-xs text-ink-400"><span>{o.business.lesson_count} activities{o.business.test ? ` · best assessment ${Math.round(o.business.test.best * 100)}%` : ""}</span><span>{o.business.percent}% complete</span></div>
        <Progress pct={o.business.percent} />
        <div className="text-xs font-medium text-brand-600 dark:text-brand-100">Enter the Business Academy →</div>
      </div>
    </Link>
  );
}

function PlacementCard({ o }: { o: Overview }) {
  return (
    <div className="card flex flex-col gap-2">
      <div className="flex items-center justify-between"><span className="text-3xl">🧭</span>{o.placement.done && <span className="text-xs text-ink-400">Last taken {fmtDate(o.placement.date)}</span>}</div>
      <div className="font-serif text-2xl">Placement and level assessment</div>
      {o.current_level ? (
        <p className="text-sm">Current level: <b>{o.current_level} — {o.current_level_name}</b>{!o.placement.done && <span className="text-ink-400"> (chosen manually)</span>}</p>
      ) : <p className="muted text-sm">You haven't been placed yet. The test takes about 40 minutes and covers grammar, vocabulary, sentence building, reading, listening, writing and speaking.</p>}
      {o.placement.last && <p className="text-xs text-ink-400">Last result: {Object.entries(o.placement.last.details.skills).map(([k, v]) => `${k.replace("_", " & ")} ${v}`).join(" · ")}</p>}
      <div className="mt-auto flex flex-wrap gap-2 pt-2">
        <Link to="/tests?start=placement" className="btn-primary">{o.placement.done ? "Retake the placement test" : "Start the placement test"}</Link>
        {o.current_level && <Link to={`/level/${o.current_level}`} className="btn-ghost">Take the {o.current_level} level test</Link>}
        <Link to="/assessments" className="btn-ghost">Review my results</Link>
      </div>
    </div>
  );
}

export function FindYourLevel() {
  const { reload } = useAcademy();
  const { setProfile } = useProfile();
  const nav = useNavigate();
  const [lv, setLv] = useState("");
  async function choose() {
    await api.post("/api/academy/choose-level", { level: lv });
    setProfile(await api.get("/api/profile"));
    reload();
    nav(`/level/${lv}`);
  }
  return (
    <div className="card space-y-4 !border-gold-500">
      <div><div className="label">Welcome to your academy</div><h2 className="font-serif text-3xl">Let's find your English level</h2>
        <p className="muted mt-1">Your programme starts at the level that fits you, so we don't place you arbitrarily. The placement test is the recommended way in.</p></div>
      <div className="grid grid-cols-2 gap-4">
        <Link to="/tests?start=placement" className="rounded-xl border border-brand-500 p-4 transition hover:bg-brand-50 dark:hover:bg-brand-500/10">
          <div className="font-medium">🧭 Take the placement test (recommended)</div>
          <p className="mt-1 text-sm text-ink-400">About 40 minutes: grammar, vocabulary, sentence construction, reading, listening, writing and speaking. You'll get a result such as “B2 — Upper Intermediate”.</p>
        </Link>
        <div className="rounded-xl border border-ink-200 p-4 dark:border-ink-800">
          <div className="font-medium">I already know my level</div>
          <p className="mt-1 text-sm text-ink-400">Choose it yourself. You can take the placement test later at any time.</p>
          <div className="mt-3 flex gap-2"><select className="input" value={lv} onChange={(e) => setLv(e.target.value)}><option value="">Choose…</option>{LEVELS.map((l) => <option key={l} value={l}>{l} — {LEVEL_NAMES[l]}</option>)}</select>
            <button className="btn-ghost" disabled={!lv} onClick={choose}>Start</button></div>
          <p className="mt-2 text-xs text-ink-400">Complete beginner? Level A1 is open without a test.</p>
        </div>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ items
export function ItemRow({ it, locked }: { it: Item; locked?: boolean }) {
  const inner = (
    <div className={`flex items-center justify-between gap-3 rounded-xl border px-3 py-2.5 text-sm transition ${!it.available ? "border-dashed border-ink-200 opacity-60 dark:border-ink-800" : it.done ? "border-emerald-500/40" : "border-ink-200 hover:border-brand-400 dark:border-ink-800"}`}>
      <span className="flex min-w-0 items-center gap-3"><span className="text-lg">{ICON[it.kind]}</span>
        <span className="min-w-0"><span className="block truncate font-medium">{it.title}</span><span className="block truncate text-xs text-ink-400">{KIND[it.kind]}{it.detail && it.kind !== "writing" ? ` · ${it.detail}` : ""}</span></span></span>
      <span className="flex shrink-0 items-center gap-2 text-xs">
        {it.score != null && <span className="text-ink-400">{Math.round(it.score * 100)}%</span>}
        {!it.available ? <span className="pill bg-gold-400/20">Coming soon</span> : locked ? <span className="text-ink-400">🔒</span> : it.done ? <span className="text-emerald-500">✓ Done</span> : <span className="text-brand-500">Start →</span>}
      </span>
    </div>
  );
  return it.available && !locked && it.route ? <Link to={it.route}>{inner}</Link> : inner;
}

// ------------------------------------------------------------------ level page
export function LevelPage() {
  const { code = "A1" } = useParams();
  const { reload } = useAcademy();
  const [d, setD] = useState<LevelDetail | null>(null);
  const [testing, setTesting] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const load = () => api.get<LevelDetail>(`/api/academy/level/${code}`).then(setD).catch((e) => setErr(e.message));
  useEffect(() => { setD(null); setTesting(false); load(); }, [code]); // eslint-disable-line
  if (err) return <ErrorBox msg={err} />;
  if (!d) return <div className="text-ink-400">Loading…</div>;
  const locked = d.status === "locked";
  const idx = LEVELS.indexOf(code);

  if (testing) return <LevelTest title={`${d.code} level test`} url={`/api/academy/level/${code}/test`} onExit={() => { setTesting(false); load(); reload(); }} />;
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex items-center justify-between text-sm">
        {idx > 0 ? <Link to={`/level/${LEVELS[idx - 1]}`} className="text-brand-500">← {LEVELS[idx - 1]}</Link> : <span />}
        <Link to="/" className="text-ink-400">Dashboard</Link>
        {idx < 5 ? <Link to={`/level/${LEVELS[idx + 1]}`} className="text-brand-500">{LEVELS[idx + 1]} →</Link> : <span />}
      </div>
      <div className="flex items-end justify-between gap-4">
        <div><div className="flex items-center gap-2"><StatusPill s={d.status} /><span className="text-xs uppercase text-ink-400">Level dashboard</span></div>
          <h1 className="h1 mt-2">{d.code} — {d.name}</h1><p className="muted mt-1">{d.description}</p></div>
        <div className="w-56 shrink-0 text-right"><div className="font-serif text-4xl">{d.percent}%</div><div className="text-xs text-ink-400">{d.done} of {d.lesson_count} activities completed</div><div className="mt-2"><Progress pct={d.percent} /></div></div>
      </div>

      {locked ? (
        <div className="card flex items-center justify-between gap-4 !border-gold-500">
          <span className="text-sm">This level is locked. You move up by passing your current level's test (≥{Math.round(d.pass_mark * 100)}%) or through the placement test. You can still read the syllabus below.</span>
          <Link to="/tests?start=placement" className="btn-primary shrink-0">Placement test</Link>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4">
          <div className="card">
            <div className="label">Continue</div>
            {d.next ? <Link to={d.next.route} className="mt-1 block font-medium text-brand-600 hover:underline dark:text-brand-100">{d.next.title} →</Link> : <p className="mt-1 text-sm">Every available activity is done. 🎉</p>}
            <p className="mt-1 text-xs text-ink-400">Activities are listed in the recommended order.</p>
          </div>
          <div className="card">
            <div className="label">{d.code} level test</div>
            <p className="text-sm">20 questions from this level's lessons and vocabulary. Pass mark {Math.round(d.pass_mark * 100)}%.{d.next_level && d.status !== "completed" ? ` Passing unlocks ${d.next_level}.` : ""}</p>
            {d.test && <p className="mt-1 text-xs text-ink-400">Best score {Math.round(d.test.best * 100)}% · {d.test.attempts} attempt{d.test.attempts > 1 ? "s" : ""}{d.test.passed ? " · passed ✓" : ""}</p>}
            <button className="btn-primary mt-3" onClick={() => setTesting(true)}>{d.test ? "Retake the level test" : "Take the level test"}</button>
          </div>
        </div>
      )}

      {d.units.map((u) => (
        <div key={u.title} className="card">
          <div className="mb-3 flex items-center justify-between"><h2 className="font-semibold">{u.title}</h2><span className="text-xs text-ink-400">{u.items.filter((i) => i.done).length}/{u.items.filter((i) => i.available).length}</span></div>
          <div className="space-y-2">{u.items.map((it) => <ItemRow key={it.key} it={it} locked={locked} />)}</div>
        </div>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ level / business test
interface TItem { key: string; type: "mcq" | "gap"; prompt: string; options: string[] | null; topic: string }
interface TResult { score: number; passed: boolean; pass_mark: number; promoted_to?: string | null; promoted_name?: string | null; weak_topics: string[]; review: { key: string; correct: boolean; given: string; answer: string; explanation: string; topic: string }[] }

export function LevelTest({ title, url, onExit }: { title: string; url: string; onExit: () => void }) {
  const { setProfile } = useProfile();
  const [items, setItems] = useState<TItem[] | null>(null);
  const [ans, setAns] = useState<Record<string, string>>({});
  const [res, setRes] = useState<TResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [t0] = useState(Date.now());
  useEffect(() => { api.get<{ items: TItem[] }>(url).then((r) => setItems(r.items)).catch((e: ApiError) => setErr(e.message)); }, [url]);
  async function submit() {
    setBusy(true);
    try {
      const all = Object.fromEntries(items!.map((i) => [i.key, ans[i.key] ?? ""]));
      setRes(await api.post<TResult>(url, { answers: all, seconds: Math.round((Date.now() - t0) / 1000) }));
      setProfile(await api.get("/api/profile"));
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }
  if (err) return <div className="mx-auto max-w-3xl space-y-3"><ErrorBox msg={err} /><button className="btn-ghost" onClick={onExit}>Back</button></div>;
  if (!items) return <div className="text-ink-400">Preparing your test…</div>;
  const answered = items.filter((i) => (ans[i.key] ?? "").trim()).length;
  if (res) return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className={`card text-center ${res.passed ? "!border-emerald-500" : "!border-gold-500"}`}>
        <div className="label">{title}</div><div className="font-serif text-6xl">{Math.round(res.score * 100)}%</div>
        <p className="mt-2 font-medium">{res.passed ? "Passed ✓" : `Not yet: the pass mark is ${Math.round(res.pass_mark * 100)}%.`}</p>
        {res.promoted_to && <p className="mt-2 text-lg">🎉 You've been promoted to <b>{res.promoted_to} — {res.promoted_name}</b>. The new level is unlocked.</p>}
        {res.weak_topics.length > 0 && <p className="mt-2 text-sm text-ink-400">Revise before retrying: {res.weak_topics.join(", ")}</p>}
      </div>
      <div className="card space-y-3">{res.review.map((r, i) => (
        <div key={r.key} className="border-t border-ink-100 pt-3 text-sm first:border-0 first:pt-0 dark:border-ink-800">
          <div><span className="text-ink-400">{i + 1}. {r.topic}</span> {r.correct ? <span className="text-emerald-500">✓</span> : <span className="text-rose-500">✗ you wrote “{r.given || "—"}”</span>}</div>
          {!r.correct && <div>Answer: <b>{r.answer}</b> · <span className="text-ink-400">{r.explanation}</span></div>}
        </div>))}</div>
      <div className="flex gap-2">{res.promoted_to && <Link to={`/level/${res.promoted_to}`} className="btn-primary">Start {res.promoted_to}</Link>}<button className="btn-ghost" onClick={onExit}>Back to the level</button></div>
    </div>
  );
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="flex items-end justify-between"><div><h1 className="h1">{title}</h1><p className="muted mt-1">Answer every question, then submit. Your result is saved in your assessment history.</p></div><button className="btn-ghost" onClick={onExit}>Cancel</button></div>
      <div className="card space-y-5">{items.map((q, n) => (
        <div key={q.key} className="border-t border-ink-100 pt-4 first:border-0 first:pt-0 dark:border-ink-800">
          <div className="mb-2 text-sm"><span className="text-ink-400">{n + 1}. {q.type === "gap" ? "Fill the gap:" : ""}</span> <span className="font-medium">{q.prompt}</span></div>
          {q.options ? (
            <div className="grid grid-cols-2 gap-1.5">{q.options.map((o) => <label key={o} className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-1.5 text-sm ${ans[q.key] === o ? "border-brand-500 bg-brand-50 dark:bg-brand-500/10" : "border-ink-200 dark:border-ink-800"}`}><input type="radio" className="hidden" checked={ans[q.key] === o} onChange={() => setAns((a) => ({ ...a, [q.key]: o }))} />{o}</label>)}</div>
          ) : <input className="input" value={ans[q.key] ?? ""} onChange={(e) => setAns((a) => ({ ...a, [q.key]: e.target.value }))} />}
        </div>))}</div>
      <div className="flex items-center justify-between"><span className="text-sm text-ink-400">{answered}/{items.length} answered</span><button className="btn-primary" disabled={busy || answered < items.length} onClick={submit}>{busy ? "Marking…" : "Submit the test"}</button></div>
    </div>
  );
}

// ------------------------------------------------------------------ business academy
interface Cat { id: string; title: string; icon: string; level: string; items: Item[]; lesson_count: number; done: number; percent: number; summary: string }
interface Biz { categories: Cat[]; summary: Overview["business"]; pass_mark: number }

export function BusinessAcademy() {
  const { reload } = useAcademy();
  const [d, setD] = useState<Biz | null>(null);
  const [testing, setTesting] = useState(false);
  const load = () => api.get<Biz>("/api/academy/business").then(setD);
  useEffect(() => { load(); }, []);
  if (testing) return <LevelTest title="Business English assessment" url="/api/academy/business/test" onExit={() => { setTesting(false); load(); reload(); }} />;
  if (!d) return <div className="text-ink-400">Loading…</div>;
  const next = d.categories.flatMap((c) => c.items).find((i) => i.available && !i.done);
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div><div className="label">Separate programme · intermediate to advanced</div><h1 className="h1">Business English Academy</h1>
          <p className="muted mt-1">18 professional categories. Each one has a lesson with exercises, plus listening, reading, vocabulary, writing and AI role-play simulations where available.</p></div>
        <div className="w-56 shrink-0 text-right"><div className="font-serif text-4xl">{d.summary.percent}%</div><div className="text-xs text-ink-400">{d.summary.done} of {d.summary.lesson_count} activities</div><div className="mt-2"><Progress pct={d.summary.percent} /></div></div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="card"><div className="label">Learning path</div>
          {next ? <Link to={next.route!} className="mt-1 block font-medium text-brand-600 hover:underline dark:text-brand-100">Next: {next.title} →</Link> : <p className="text-sm">Every activity is done. 🎉</p>}
          <p className="mt-1 text-xs text-ink-400">Categories follow a recommended order: communication first, then specialist fields.</p></div>
        <div className="card"><div className="label">Business assessment</div>
          <p className="text-sm">24 questions across all categories. Pass mark {Math.round(d.pass_mark * 100)}%.</p>
          {d.summary.test && <p className="mt-1 text-xs text-ink-400">Best {Math.round(d.summary.test.best * 100)}% · {d.summary.test.attempts} attempt(s){d.summary.test.passed ? " · passed ✓" : ""}</p>}
          <button className="btn-primary mt-3" onClick={() => setTesting(true)}>Take the assessment</button></div>
      </div>
      <div className="grid grid-cols-3 gap-4">{d.categories.map((c, i) => (
        <Link key={c.id} to={`/business/${c.id}`} className="card flex flex-col gap-2 transition hover:border-brand-400">
          <div className="flex items-center justify-between"><span className="text-2xl">{c.icon}</span><span className="text-xs text-ink-400">{i + 1}/18 · {c.level}</span></div>
          <div className="font-serif text-lg leading-tight">{c.title}</div>
          <p className="muted line-clamp-2 text-xs">{c.summary}</p>
          <div className="mt-auto space-y-1 pt-1"><div className="flex justify-between text-xs text-ink-400"><span>{c.lesson_count} activities</span><span>{c.percent}%</span></div><Progress pct={c.percent} /></div>
        </Link>))}</div>
    </div>
  );
}

export function BusinessCategory() {
  const { id } = useParams();
  const [d, setD] = useState<Biz | null>(null);
  useEffect(() => { api.get<Biz>("/api/academy/business").then(setD); }, []);
  if (!d) return <div className="text-ink-400">Loading…</div>;
  const i = d.categories.findIndex((c) => c.id === id);
  const c = d.categories[i];
  if (!c) return <ErrorBox msg="Unknown category" />;
  const prev = d.categories[i - 1], next = d.categories[i + 1];
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex justify-between text-sm"><Link to="/business" className="text-brand-500">← Business Academy</Link>{next && <Link to={`/business/${next.id}`} className="text-brand-500">{next.title} →</Link>}</div>
      <div className="flex items-end justify-between">
        <div><div className="flex items-center gap-2"><span className="text-3xl">{c.icon}</span><LevelPill l={c.level} /></div><h1 className="h1 mt-2">{c.title}</h1><p className="muted mt-1">{c.summary}</p></div>
        <div className="text-right"><div className="font-serif text-3xl">{c.percent}%</div><div className="text-xs text-ink-400">{c.done}/{c.lesson_count} done</div></div>
      </div>
      <div className="card space-y-2">{c.items.map((it) => <ItemRow key={it.key} it={it} />)}</div>
      {prev && <Link to={`/business/${prev.id}`} className="text-sm text-brand-500">← {prev.title}</Link>}
    </div>
  );
}

// ------------------------------------------------------------------ assessment history
export function Assessments() {
  const [rows, setRows] = useState<{ id: number; kind: string; level: string; score: number; passed: boolean; date: string; details: Record<string, unknown> | null }[] | null>(null);
  useEffect(() => { api.get<typeof rows>("/api/academy/assessments").then(setRows); }, []);
  if (!rows) return <div className="text-ink-400">Loading…</div>;
  const label = (k: string) => (k === "placement" ? "Placement test" : k === "business" ? "Business assessment" : "Level test");
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div><h1 className="h1">My assessment results</h1><p className="muted mt-1">Every placement test, level test and Business Academy assessment you've taken.</p></div>
      {rows.length === 0 ? <div className="card"><p className="muted">No assessments yet.</p><Link to="/tests?start=placement" className="btn-primary mt-3 inline-block">Take the placement test</Link></div> : (
        <div className="card divide-y divide-ink-100 dark:divide-ink-800">{rows.map((r) => {
          const d = r.details as { skills?: Record<string, string>; weak_topics?: string[]; promoted_to?: string } | null;
          return (
            <div key={r.id} className="flex items-start justify-between gap-4 py-3 text-sm">
              <div><div className="font-medium">{label(r.kind)}{r.kind === "level_test" && ` · ${r.level}`}</div>
                <div className="text-xs text-ink-400">{fmtDate(r.date)}
                  {d?.skills && ` · ${Object.entries(d.skills).map(([k, v]) => `${k.replace("_", " & ")} ${v}`).join(", ")}`}
                  {d?.weak_topics?.length ? ` · revise: ${d.weak_topics.join(", ")}` : ""}
                  {d?.promoted_to ? ` · promoted to ${d.promoted_to}` : ""}</div></div>
              <div className="text-right">{r.kind === "placement" ? <span className="font-serif text-xl">{r.level} — {LEVEL_NAMES[r.level]}</span>
                : <><span className="font-serif text-xl">{Math.round(r.score * 100)}%</span><div className={`text-xs ${r.passed ? "text-emerald-500" : "text-ink-400"}`}>{r.passed ? "passed" : "not passed"}</div></>}</div>
            </div>);
        })}</div>)}
    </div>
  );
}
