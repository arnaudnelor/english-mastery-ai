import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useAcademy, useProfile } from "../App";
import { AcademyAreas } from "./Academy";
import { Bar, CategoryPill, ErrorBox } from "../components/ui";

interface Dash {
  estimated_cefr: string;
  skills: Record<string, number | null>;
  weaknesses: { category: string; pattern: string; count: number }[];
  vocabulary: { total: number; due: number; mastered: number; learning: number; often_forgotten: number };
  minutes_week: number; minutes_month: number; streak_days: number;
  daily_plan: { skill: string; minutes: number; reason: string; route: string }[];
  completed_total?: number; in_progress_total?: number; minutes_total?: number;
  performance_week?: { activities: number; average: number | null }; performance_month?: { activities: number; average: number | null };
  recent?: { title: string; route: string | null; status: string; score: number | null; level: string | null; date: string }[];
}

const LIVE = new Set(["/conversation", "/grammar", "/vocabulary", "/writing", "/reading", "/listening", "/pronunciation", "/video"]);

export default function Dashboard() {
  const { profile } = useProfile();
  const { overview } = useAcademy();
  const [d, setD] = useState<Dash | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [cont, setCont] = useState<{ route: string; title: string; reason: string } | null>(null);
  useEffect(() => {
    api.get<Dash>("/api/profile/dashboard").then(setD).catch((e) => setErr(e.message));
    api.get<typeof cont>("/api/academy/continue").then(setCont).catch(() => {});
  }, []);

  if (err) return <ErrorBox msg={err} />;
  if (!d) return <div className="text-ink-400">Loading…</div>;
  const hour = new Date().getHours();
  const greet = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="h1">{greet}, {profile.name}.</h1><p className="muted mt-1">Your academy: six CEFR levels, the Business English Academy and your assessments.</p></div>
        {cont ? <Link to={cont.route} className="btn-primary !px-5 !py-3 text-base" title={cont.title}>▶ CONTINUE LEARNING<span className="block text-xs font-normal opacity-80">{cont.title.slice(0, 60)}</span></Link>
          : overview?.next ? <Link to={overview.next.route} className="btn-primary">Continue: {overview.next.title}</Link> : <Link to="/conversation" className="btn-primary">Start speaking practice</Link>}
      </div>

      <AcademyAreas />
      {d.completed_total !== undefined && <ProgressPanel d={d} />}
      <h2 className="pt-2 font-serif text-2xl">Your statistics and daily practice</h2>
      <div className="grid grid-cols-4 gap-4">
        {[
          ["Academy level", overview?.current_level ?? "Not placed", overview?.current_level ? `${overview.current_level_name} · skills estimate ${d.estimated_cefr}` : "take the placement test"],
          ["Streak", `${d.streak_days} day${d.streak_days === 1 ? "" : "s"}`, "keep it going"],
          ["This week", `${d.minutes_week} min`, `${d.minutes_month} min this month`],
          ["Vocabulary", `${d.vocabulary.mastered} mastered`, `${d.vocabulary.due} due · ${d.vocabulary.total} in deck`],
        ].map(([a, b, c]) => (
          <div key={a} className="card"><div className="label">{a}</div><div className="font-serif text-2xl">{b}</div><div className="mt-1 text-xs text-ink-400">{c}</div></div>
        ))}
      </div>

      <div className="grid grid-cols-5 gap-6">
        <div className="card col-span-3">
          <h2 className="mb-4 font-semibold">Today's plan · {profile.daily_minutes} minutes</h2>
          <ol className="space-y-2">
            {d.daily_plan.map((p) => {
              const live = LIVE.has(p.route);
              const inner = (
                <div className={`flex items-center justify-between rounded-xl border p-3 ${live ? "border-ink-200 hover:border-brand-400 dark:border-ink-800" : "border-dashed border-ink-200 opacity-60 dark:border-ink-800"}`}>
                  <div><div className="font-medium capitalize">{p.skill}</div><div className="text-xs text-ink-400">{p.reason}{!live && " · module coming soon — use AI Conversation meanwhile"}</div></div>
                  <span className="text-sm text-ink-600 dark:text-ink-400">{p.minutes} min</span>
                </div>
              );
              return <li key={p.skill}>{live ? <Link to={p.route}>{inner}</Link> : <Link to="/conversation">{inner}</Link>}</li>;
            })}
          </ol>
        </div>
        <div className="col-span-2 space-y-6">
          <div className="card space-y-3">
            <h2 className="font-semibold">Skills (last 30 days)</h2>
            {Object.entries(d.skills).map(([k, v]) => <Bar key={k} label={k} value={v} />)}
          </div>
          <div className="card">
            <h2 className="mb-3 font-semibold">Recurring mistakes</h2>
            {d.weaknesses.length === 0 ? <p className="muted">None tracked yet. Have a conversation or do some exercises.</p> : (
              <ul className="space-y-2">{d.weaknesses.map((w) => (
                <li key={w.pattern} className="flex items-center justify-between gap-2 text-sm"><span className="flex items-center gap-2"><CategoryPill c={w.category} />{w.pattern}</span><span className="text-ink-400">×{w.count}</span></li>
              ))}</ul>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function ProgressPanel({ d }: { d: Dash }) {
  const { overview } = useAcademy();
  const cur = overview?.levels.find((l) => l.status === "current");
  const pct = (v: number | null | undefined) => (v == null ? "—" : `${Math.round(v * 100)}%`);
  const upcoming: [string, string, string][] = [];
  if (overview && !overview.level_confirmed) upcoming.push(["Placement test", "Find your level (A1–C2)", "/tests?start=placement"]);
  if (cur) upcoming.push([`${cur.code} level test`, cur.test?.passed ? "Passed" : cur.test ? `Best ${Math.round(cur.test.best * 100)}% so far` : `Passing it unlocks ${cur.code === "C2" ? "the completion of C2" : "the next level"}`, `/level/${cur.code}`]);
  upcoming.push(["Weekly progress check", "12 questions on your mistakes and words", "/tests"]);
  if (overview && overview.business.done > 0) upcoming.push(["Business English assessment", overview.business.test ? `Best ${Math.round(overview.business.test.best * 100)}%` : "Not taken yet", "/business"]);
  return (
    <section className="grid gap-4 lg:grid-cols-3">
      <div className="card space-y-2">
        <h2 className="font-semibold">My progress</h2>
        <div className="grid grid-cols-2 gap-2 text-sm">
          <div><div className="label">Completed</div><div className="font-serif text-2xl">{d.completed_total}</div></div>
          <div><div className="label">Remaining ({cur?.code ?? "level"})</div><div className="font-serif text-2xl">{cur ? cur.lesson_count - cur.done : "—"}</div></div>
          <div><div className="label">Total study</div><div className="font-serif text-2xl">{Math.floor((d.minutes_total ?? 0) / 60)}h {(d.minutes_total ?? 0) % 60}m</div></div>
          <div><div className="label">Overall ({cur?.code ?? "—"})</div><div className="font-serif text-2xl">{cur ? `${cur.percent}%` : "—"}</div></div>
          <div><div className="label">This week</div><div>{d.performance_week?.activities ?? 0} activities · {pct(d.performance_week?.average)}</div></div>
          <div><div className="label">This month</div><div>{d.performance_month?.activities ?? 0} activities · {pct(d.performance_month?.average)}</div></div>
        </div>
      </div>
      <div className="card">
        <h2 className="mb-2 font-semibold">Recent activities</h2>
        {!d.recent?.length ? <p className="muted">Nothing yet: open your first lesson.</p> : (
          <ul className="space-y-1.5 text-sm">{d.recent.map((r, i) => (
            <li key={i} className="flex items-center justify-between gap-2"><Link className="truncate hover:text-brand-500" to={r.route ?? "/"}>{r.title}</Link>
              <span className={`shrink-0 text-xs ${r.status === "completed" ? "text-emerald-500" : "text-ink-400"}`}>{r.status === "completed" ? `✓ ${pct(r.score)}` : "in progress"}</span></li>))}</ul>)}
      </div>
      <div className="card">
        <h2 className="mb-2 font-semibold">Upcoming assessments</h2>
        <ul className="space-y-2 text-sm">{upcoming.map(([t, s, r]) => <li key={t}><Link to={r} className="hover:text-brand-500"><b>{t}</b><span className="block text-xs text-ink-400">{s}</span></Link></li>)}</ul>
      </div>
    </section>
  );
}
