import { useEffect, useState } from "react";
import { api } from "../lib/api";

interface BM { id: number; kind: string; item_id: string }

export function BookmarkButton({ kind, itemId, title, route }: { kind: string; itemId: string; title: string; route: string }) {
  const [id, setId] = useState<number | null>(null);
  useEffect(() => { api.get<BM[]>("/api/bookmarks").then((b) => setId(b.find((x) => x.kind === kind && x.item_id === itemId)?.id ?? null)).catch(() => {}); }, [kind, itemId]);
  async function toggle() {
    if (id) { await api.del(`/api/bookmarks/${id}`); setId(null); }
    else setId((await api.post<{ id: number }>("/api/bookmarks", { kind, item_id: itemId, title, route })).id);
  }
  return <button onClick={toggle} title={id ? "Remove bookmark" : "Bookmark"} className={`btn-ghost !px-2 !py-1 text-xs ${id ? "!border-gold-500 text-gold-500" : ""}`}>{id ? "★ Bookmarked" : "☆ Bookmark"}</button>;
}
