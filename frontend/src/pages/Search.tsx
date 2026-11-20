import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import { LevelPill } from "../components/ui";

export default function Search() {
  const [params] = useSearchParams();
  const q = params.get("q") ?? "";
  const [hits, setHits] = useState<{ kind: string; title: string; level: string; route: string }[] | null>(null);
  useEffect(() => { setHits(null); api.get<typeof hits>(`/api/search?q=${encodeURIComponent(q)}`).then(setHits); }, [q]);
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <h1 className="h1">Search: “{q}”</h1>
      {hits == null ? <p className="text-ink-400">Searching…</p> : hits.length === 0 ? <p className="muted">No results. Try another word, a grammar topic, or a French word.</p> : (
        <div className="card divide-y divide-ink-100 !p-2 dark:divide-ink-800">{hits.map((h, i) => (
          <Link key={i} to={h.route} className="flex items-center justify-between px-3 py-2 hover:bg-ink-50 dark:hover:bg-ink-800/50"><span><span className="mr-2 text-xs uppercase text-ink-400">{h.kind}</span>{h.title}</span>{h.level && <LevelPill l={h.level} />}</Link>
        ))}</div>
      )}
    </div>
  );
}
