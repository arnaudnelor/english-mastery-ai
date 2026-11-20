import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { LevelPill } from "../components/ui";

interface Unit { kind: string; id: string; title: string; level: string; route: string; done: boolean; priority: number }
interface PathData { levels: string[]; weeks: { week: number; units: Unit[] }[]; completed: number; total: number; placement_done: boolean }
const ICON: Record<string, string> = { grammar: "📘", reading: "📰", listening: "🎧", speaking: "🎙" };

export default function Path() {
  const [d, setD] = useState<PathData | null>(null);
  const [bm, setBm] = useState<{ id: number; kind: string; title: string; route: string }[]>([]);
  useEffect(() => { api.get<PathData>("/api/path").then(setD); api.get<typeof bm>("/api/bookmarks").then(setBm); }, []);
  if (!d) return <div className="text-ink-400">Loading…</div>;
  const pct = Math.round((d.completed / Math.max(1, d.total)) * 100);
  const firstOpen = d.weeks.findIndex((w) => w.units.some((u) => !u.done && u.kind !== "speaking"));
  return (
    <div className="mx-auto grid max-w-6xl grid-cols-[1fr_300px] gap-6">
      <div className="space-y-6">
        <div><h1 className="h1">My Learning Path</h1><p className="muted mt-1">A week-by-week route from {d.levels[0]} to {d.levels[d.levels.length - 1]}. Topics behind your recurring mistakes come first, and each week ends with a speaking role-play.</p></div>
        {!d.placement_done && <div className="card flex items-center justify-between !border-gold-500"><span>Take the placement test so your path starts at the right level.</span><Link to="/tests" className="btn-primary">Take placement test</Link></div>}
        <div className="card"><div className="mb-2 flex justify-between text-sm"><span>{d.completed} of {d.total} units completed</span><span>{pct}%</span></div><div className="h-2 rounded-full bg-ink-100 dark:bg-ink-800"><div className="h-2 rounded-full bg-brand-500" style={{ width: `${pct}%` }} /></div></div>
        {d.weeks.map((w, i) => (
          <div key={w.week} className={`card ${i === firstOpen ? "!border-brand-500" : ""}`}>
            <div className="mb-3 flex items-center justify-between"><h2 className="font-semibold">Week {w.week}{i === firstOpen && <span className="ml-2 pill bg-brand-600 text-white">current</span>}</h2><span className="text-xs text-ink-400">{w.units.filter((u) => u.done).length}/{w.units.length}</span></div>
            <div className="grid grid-cols-1 gap-2">{w.units.map((u) => (
              <Link key={u.kind + u.id} to={u.route} className={`flex items-center justify-between rounded-xl border px-3 py-2 text-sm transition hover:border-brand-400 ${u.done ? "border-emerald-500/40 opacity-70" : "border-ink-200 dark:border-ink-800"}`}>
                <span className="flex items-center gap-2"><span>{ICON[u.kind]}</span>{u.title}{u.priority > 0 && <span className="pill bg-rose-100 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300">your mistakes</span>}</span>
                <span className="flex items-center gap-2"><LevelPill l={u.level} />{u.done ? <span className="text-emerald-500">✓</span> : <span className="text-ink-400">→</span>}</span>
              </Link>
            ))}</div>
          </div>
        ))}
      </div>
      <aside className="space-y-4">
        <div className="card sticky top-0"><h2 className="mb-3 font-semibold">★ Bookmarks</h2>
          {bm.length === 0 ? <p className="muted">Use ☆ Bookmark on lessons, texts, recordings and videos to keep them here.</p>
            : <ul className="space-y-2 text-sm">{bm.map((b) => <li key={b.id}><Link to={b.route} className="hover:text-brand-500"><span className="text-xs uppercase text-ink-400">{b.kind}</span><br />{b.title}</Link></li>)}</ul>}
        </div>
      </aside>
    </div>
  );
}
