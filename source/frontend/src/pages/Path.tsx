import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { LevelPill } from "../components/ui";
import { FindYourLevel, Item, ItemRow, StatusPill } from "./Academy";

interface PathData {
  level_confirmed: boolean; placement_done: boolean; level?: string; level_name?: string; status?: string;
  units?: { title: string; items: Item[] }[]; completed?: number; total?: number; next?: { title: string; route: string } | null;
  test?: { best: number; passed: boolean; attempts: number } | null; revision?: (Item & { level: string; reason: string })[];
}

export default function Path() {
  const [d, setD] = useState<PathData | null>(null);
  const [bm, setBm] = useState<{ id: number; kind: string; title: string; route: string }[]>([]);
  useEffect(() => { api.get<PathData>("/api/path").then(setD); api.get<typeof bm>("/api/bookmarks").then(setBm); }, []);
  if (!d) return <div className="text-ink-400">Loading…</div>;
  if (!d.level_confirmed) return <div className="mx-auto max-w-5xl space-y-6"><h1 className="h1">My Learning Path</h1><FindYourLevel /></div>;
  const pct = Math.round((d.completed! / Math.max(1, d.total!)) * 100);
  const firstOpen = d.units!.findIndex((u) => u.items.some((i) => i.available && !i.done));
  return (
    <div className="mx-auto grid max-w-6xl grid-cols-[1fr_300px] gap-6">
      <div className="space-y-6">
        <div><div className="flex items-center gap-2"><StatusPill s={d.status!} /><span className="text-xs uppercase text-ink-400">Your current programme</span></div>
          <h1 className="h1 mt-2">My Learning Path · {d.level} — {d.level_name}</h1>
          <p className="muted mt-1">Work through the units in order. When you're ready, the {d.level} level test (pass mark 70%) moves you up to the next level. Lessons alone don't promote you; your test results do.</p></div>
        <div className="card space-y-2">
          <div className="flex justify-between text-sm"><span>{d.completed} of {d.total} activities completed</span><span>{pct}%</span></div>
          <div className="h-2 rounded-full bg-ink-100 dark:bg-ink-800"><div className="h-2 rounded-full bg-brand-500" style={{ width: `${pct}%` }} /></div>
          <div className="flex flex-wrap items-center gap-2 pt-1">
            {d.next && <Link to={d.next.route} className="btn-primary">Next: {d.next.title}</Link>}
            <Link to={`/level/${d.level}`} className="btn-ghost">{d.test ? `Level test · best ${Math.round(d.test.best * 100)}%` : "Take the level test"}</Link>
            {!d.placement_done && <Link to="/tests?start=placement" className="btn-ghost">Confirm with the placement test</Link>}
          </div>
        </div>
        {d.units!.map((u, i) => (
          <div key={u.title} className={`card ${i === firstOpen ? "!border-brand-500" : ""}`}>
            <div className="mb-3 flex items-center justify-between"><h2 className="font-semibold">{u.title}{i === firstOpen && <span className="ml-2 pill bg-brand-600 text-white">current</span>}</h2><span className="text-xs text-ink-400">{u.items.filter((x) => x.done).length}/{u.items.filter((x) => x.available).length}</span></div>
            <div className="space-y-2">{u.items.map((it) => <ItemRow key={it.key} it={it} />)}</div>
          </div>
        ))}
      </div>
      <aside className="space-y-4">
        <div className="card"><h2 className="mb-3 font-semibold">Recommended revision</h2>
          {d.revision!.length === 0 ? <p className="muted">Nothing to revise yet. Lessons with a score under 70%, or linked to your recurring mistakes, will appear here.</p>
            : <ul className="space-y-2 text-sm">{d.revision!.map((r) => <li key={r.key}><Link to={r.route!} className="hover:text-brand-500"><LevelPill l={r.level} /> {r.title}<br /><span className="text-xs text-ink-400">{r.reason}</span></Link></li>)}</ul>}
        </div>
        <div className="card"><h2 className="mb-3 font-semibold">★ Bookmarks</h2>
          {bm.length === 0 ? <p className="muted">Use ☆ Bookmark on lessons, texts, recordings and videos to keep them here.</p>
            : <ul className="space-y-2 text-sm">{bm.map((b) => <li key={b.id}><Link to={b.route} className="hover:text-brand-500"><span className="text-xs uppercase text-ink-400">{b.kind}</span><br />{b.title}</Link></li>)}</ul>}
        </div>
      </aside>
    </div>
  );
}
