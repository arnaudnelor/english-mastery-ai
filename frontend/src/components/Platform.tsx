import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, SaveState, saveStatus } from "../lib/api";

/** "Saving… / Saved successfully / Unable to save — retrying", always visible while something is being written. */
export function SaveIndicator() {
  const [s, setS] = useState<SaveState>(saveStatus.get());
  useEffect(() => saveStatus.subscribe(setS), []);
  if (s === "idle") return null;
  const map: Record<Exclude<SaveState, "idle">, [string, string]> = {
    saving: ["Saving…", "bg-ink-100 text-ink-700 dark:bg-ink-800 dark:text-ink-200"],
    saved: ["✓ Saved successfully", "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300"],
    retrying: ["Unable to save — retrying", "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-200"],
    waking: ["Connecting to the academy server…", "bg-ink-100 text-ink-700 dark:bg-ink-800 dark:text-ink-200"],
  };
  const [label, cls] = map[s];
  return <div role="status" aria-live="polite" className={`fixed bottom-4 right-4 z-50 rounded-full px-4 py-2 text-sm shadow-lg ${cls}`}>{label}</div>;
}

interface Note { id: number; kind: string; title: string; body: string; route: string | null; read: boolean; date: string }

export function NotificationBell() {
  const [data, setData] = useState<{ unread: number; items: Note[] }>({ unread: 0, items: [] });
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const load = () => api.get<typeof data>("/api/auth/notifications").then(setData).catch(() => {});
  useEffect(() => { load(); const t = window.setInterval(load, 120000); return () => window.clearInterval(t); }, []);
  useEffect(() => {
    const close = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);
  return (
    <div className="relative" ref={ref}>
      <button aria-label="Notifications" className="relative rounded-lg px-2 py-1 hover:bg-ink-50 dark:hover:bg-ink-800" onClick={async () => {
        setOpen(!open);
        if (!open && data.unread) { await api.post("/api/auth/notifications/read"); setData((d) => ({ unread: 0, items: d.items })); }
      }}>🔔{data.unread > 0 && <span className="absolute -right-1 -top-1 rounded-full bg-rose-500 px-1.5 text-[10px] text-white">{data.unread}</span>}</button>
      {open && (
        <div className="absolute left-0 z-50 mt-2 max-h-96 w-80 overflow-y-auto rounded-xl border border-ink-200 bg-white p-2 shadow-xl dark:border-ink-800 dark:bg-ink-900">
          {data.items.length === 0 ? <p className="p-3 text-sm text-ink-400">No notifications yet.</p> : data.items.map((n) => {
            const inner = <div className={`rounded-lg p-2 text-sm ${n.read ? "" : "bg-brand-50 dark:bg-brand-500/10"}`}><div className="font-medium">{n.title}</div>{n.body && <div className="text-xs text-ink-400">{n.body}</div>}<div className="text-[10px] text-ink-400">{new Date(n.date + "Z").toLocaleString()}</div></div>;
            return <div key={n.id} onClick={() => setOpen(false)}>{n.route ? <Link to={n.route}>{inner}</Link> : inner}</div>;
          })}
        </div>
      )}
    </div>
  );
}
