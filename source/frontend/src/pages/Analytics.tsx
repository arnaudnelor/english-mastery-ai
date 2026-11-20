import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { BarChart } from "../components/BarChart";
import { CategoryPill } from "../components/ui";

interface A {
  weeks: string[]; minutes_per_week: number[]; skills_per_week: Record<string, (number | null)[]>; mistakes_by_category: Record<string, number>; mistakes_per_week: number[];
  top_mistakes: { category: string; pattern: string; count: number }[]; vocabulary: { total: number; due: number; new: number; learning: number; mastered: number; often_forgotten: number };
  exams: { date: string; overall: number; bands: Record<string, number> | null }[]; totals: { hours: number; activities: number; conversations: number; streak: number };
  skills_now: Record<string, number | null>; estimated_cefr: string; history: { when: string; skill: string; item: string; score: number; minutes: number }[];
}

function Spark({ values }: { values: (number | null)[] }) {
  const pts = values.map((v, i) => (v == null ? null : [i * (120 / (values.length - 1)), 30 - v * 28] as const)).filter(Boolean) as [number, number][];
  if (pts.length < 2) return <span className="text-xs text-ink-400">not enough data</span>;
  return <svg viewBox="0 0 120 32" className="h-8 w-32"><polyline fill="none" stroke="#3a6fe0" strokeWidth={2} points={pts.map((p) => p.join(",")).join(" ")} />{pts.map(([x, y], i) => <circle key={i} cx={x} cy={y} r={1.8} fill="#3a6fe0" />)}</svg>;
}

export default function Analytics() {
  const [a, setA] = useState<A | null>(null);
  useEffect(() => { api.get<A>("/api/analytics").then(setA); }, []);
  if (!a) return <div className="text-ink-400">Loading…</div>;
  const label = (w: string) => new Date(w + "T12:00").toLocaleDateString(undefined, { month: "short", day: "numeric" });
  const last8 = a.weeks.slice(-8);
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <h1 className="h1">Progress Analytics</h1>
      <div className="grid grid-cols-5 gap-4">{[["Estimated level", a.estimated_cefr], ["Study time", `${a.totals.hours} h`], ["Activities", a.totals.activities], ["Conversations", a.totals.conversations], ["Streak", `${a.totals.streak} d`]].map(([k, v]) => (
        <div key={k as string} className="card"><div className="label">{k}</div><div className="font-serif text-2xl">{v}</div></div>))}</div>
      <div className="grid grid-cols-2 gap-6">
        <div className="card"><h2 className="mb-2 font-semibold">Study minutes per week</h2><BarChart categories={last8.map(label)} series={[{ name: "minutes", values: a.minutes_per_week.slice(-8) }]} height={220} /></div>
        <div className="card"><h2 className="mb-2 font-semibold">Mistakes detected per week</h2><BarChart categories={last8.map(label)} series={[{ name: "mistakes", values: a.mistakes_per_week.slice(-8) }]} height={220} /></div>
      </div>
      <div className="grid grid-cols-2 gap-6">
        <div className="card"><h2 className="mb-3 font-semibold">Skill trends (weekly average, 8 weeks)</h2>
          <table className="w-full text-sm"><tbody>{Object.entries(a.skills_now).map(([s, now]) => (
            <tr key={s} className="border-t border-ink-100 dark:border-ink-800"><td className="py-2 capitalize">{s}</td><td><Spark values={(a.skills_per_week[s] ?? []).slice(-8)} /></td><td className="text-right">{now == null ? "–" : `${Math.round(now * 100)}%`}</td></tr>))}</tbody></table></div>
        <div className="card space-y-4">
          <div><h2 className="mb-2 font-semibold">Mistakes by type</h2><div className="flex flex-wrap gap-2">{Object.entries(a.mistakes_by_category).map(([c, n]) => <span key={c} className="flex items-center gap-1"><CategoryPill c={c} /><b className="text-sm">{n}</b></span>)}{!Object.keys(a.mistakes_by_category).length && <span className="muted">None yet.</span>}</div></div>
          <div><h2 className="mb-2 font-semibold">Most frequent</h2><ul className="space-y-1 text-sm">{a.top_mistakes.map((m) => <li key={m.pattern} className="flex justify-between"><span>{m.pattern}</span><span className="text-ink-400">×{m.count}</span></li>)}</ul></div>
          <div><h2 className="mb-2 font-semibold">Vocabulary</h2><p className="text-sm">{a.vocabulary.mastered} mastered · {a.vocabulary.learning} learning · {a.vocabulary.often_forgotten} often forgotten · {a.vocabulary.new} new</p></div>
        </div>
      </div>
      {a.exams.length > 0 && <div className="card"><h2 className="mb-2 font-semibold">Mock exam history (practice estimates)</h2><table className="w-full text-sm"><tbody>{a.exams.map((e, i) => <tr key={i} className="border-t border-ink-100 dark:border-ink-800"><td className="py-2">{e.date}</td><td className="text-ink-400">{e.bands && Object.entries(e.bands).map(([k, v]) => `${k} ${v}`).join(" · ")}</td><td className="text-right font-serif text-lg">{e.overall}</td></tr>)}</tbody></table></div>}
      <div className="card"><h2 className="mb-2 font-semibold">Learning history</h2>
        <table className="w-full text-sm"><thead className="text-left text-xs text-ink-400"><tr><th>When</th><th>Skill</th><th>Activity</th><th className="text-right">Score</th></tr></thead><tbody>{a.history.map((h, i) => (
          <tr key={i} className="border-t border-ink-100 dark:border-ink-800"><td className="py-1.5 text-ink-400">{new Date(h.when + "Z").toLocaleString()}</td><td className="capitalize">{h.skill}</td><td className="text-ink-600 dark:text-ink-400">{h.item}</td><td className="text-right">{Math.round(h.score * 100)}%</td></tr>))}</tbody></table>
        {!a.history.length && <p className="muted">Your activity will appear here.</p>}</div>
    </div>
  );
}
