import { ReactNode } from "react";
import { speakLocal } from "../lib/speech";

const CAT: Record<string, string> = {
  grammar: "bg-rose-100 text-rose-800 dark:bg-rose-500/15 dark:text-rose-300",
  vocabulary: "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
  naturalness: "bg-violet-100 text-violet-800 dark:bg-violet-500/15 dark:text-violet-300",
  pronunciation: "bg-sky-100 text-sky-800 dark:bg-sky-500/15 dark:text-sky-300",
  fluency: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300",
};

export function CategoryPill({ c }: { c: string }) {
  return <span className={`pill ${CAT[c] ?? "bg-ink-100 text-ink-800 dark:bg-ink-800 dark:text-ink-200"}`}>{c}</span>;
}

export function LevelPill({ l }: { l: string }) {
  return <span className="pill bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-100">{l}</span>;
}

export function Speak({ text, accent = "en-CA", label }: { text: string; accent?: string; label?: string }) {
  return (
    <button
      type="button"
      title="Listen (Windows voice, works offline)"
      onClick={() => speakLocal(text, accent)}
      className="inline-flex items-center gap-1 rounded-lg px-1.5 py-0.5 text-brand-600 hover:bg-brand-50 dark:text-brand-400 dark:hover:bg-ink-800"
    >
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 5 6 9H2v6h4l5 4V5z" /><path d="M15.5 8.5a5 5 0 0 1 0 7M19 5a10 10 0 0 1 0 14" /></svg>
      {label && <span className="text-xs">{label}</span>}
    </button>
  );
}

export function ErrorBox({ msg, action }: { msg: string | null; action?: ReactNode }) {
  if (!msg) return null;
  return (
    <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-200">
      {msg} {action}
    </div>
  );
}

export function Bar({ value, label }: { value: number | null; label: string }) {
  const pct = value == null ? 0 : Math.round(value * 100);
  return (
    <div>
      <div className="mb-1 flex justify-between text-sm">
        <span className="capitalize">{label}</span>
        <span className="text-ink-400">{value == null ? "no data yet" : `${pct}%`}</span>
      </div>
      <div className="h-2 rounded-full bg-ink-100 dark:bg-ink-800">
        <div className="h-2 rounded-full bg-brand-500 transition-all" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export function Planned({ title, phase, children }: { title: string; phase: number; children?: ReactNode }) {
  return (
    <div className="mx-auto max-w-2xl">
      <div className="card text-center">
        <span className="pill bg-gold-400/20 text-gold-500">Planned · Phase {phase}</span>
        <h1 className="h1 mt-4">{title}</h1>
        <p className="muted mt-3">
          This module isn't in this release yet. Nothing on this page is clickable on purpose — every visible feature in English Mastery AI either works or is labelled like this.
        </p>
        {children && <div className="mt-6 text-left text-sm">{children}</div>}
      </div>
    </div>
  );
}
