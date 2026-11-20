import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useProfile } from "../App";
import { Bar, CategoryPill, ErrorBox } from "../components/ui";

interface Dash {
  estimated_cefr: string;
  skills: Record<string, number | null>;
  weaknesses: { category: string; pattern: string; count: number }[];
  vocabulary: { total: number; due: number; mastered: number; learning: number; often_forgotten: number };
  minutes_week: number; minutes_month: number; streak_days: number;
  daily_plan: { skill: string; minutes: number; reason: string; route: string }[];
}

const LIVE = new Set(["/conversation", "/grammar", "/vocabulary", "/writing", "/reading", "/listening", "/pronunciation", "/video"]);

export default function Dashboard() {
  const { profile } = useProfile();
  const [d, setD] = useState<Dash | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { api.get<Dash>("/api/profile/dashboard").then(setD).catch((e) => setErr(e.message)); }, []);

  if (err) return <ErrorBox msg={err} />;
  if (!d) return <div className="text-ink-400">Loading…</div>;
  const hour = new Date().getHours();
  const greet = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex items-end justify-between">
        <div><h1 className="h1">{greet}, {profile.name}.</h1><p className="muted mt-1">Here's today's session, built around your weak spots.</p></div>
        <Link to="/conversation" className="btn-primary">Start speaking practice</Link>
      </div>

      {!profile.placement_done && (
        <div className="card flex items-center justify-between !border-gold-500 !py-4"><span>New here? A 40-minute placement test sets your real level and builds your learning path.</span><Link to="/tests" className="btn-primary">Take the placement test</Link></div>
      )}
      <div className="grid grid-cols-4 gap-4">
        {[
          ["Estimated level", d.estimated_cefr, `target ${profile.target_level}`],
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
