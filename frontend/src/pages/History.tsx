import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, Feedback } from "../lib/api";
import { CategoryPill } from "../components/ui";

interface Conv { id: number; mode: string; title: string; started_at: string; turns: number; has_summary: boolean; estimated_cefr?: string | null }
interface ConvFull { id: number; title: string; started_at: string; summary: Record<string, any> | null; messages: { role: string; content: string; feedback: Feedback | null }[] } // eslint-disable-line @typescript-eslint/no-explicit-any
interface Mistake { when: string; category: string; pattern: string; original: string; corrected: string; explanation: string; source: string }
interface Attempt { id: number; exam_id: string; started_at: string; finished: boolean; overall_band: number | null; bands: Record<string, number> | null }
interface Act { when: string; skill: string; item: string; score: number; minutes: number }

const when = (iso: string) => new Date(iso.endsWith("Z") ? iso : iso + "Z").toLocaleString();
const EXAM: Record<string, string> = { "ielts-academic-1": "IELTS Academic", "toefl-2026-1": "TOEFL iBT (2026)", "cambridge-c1-1": "Cambridge C1 Advanced", "cambridge-c2-1": "Cambridge C2 Proficiency" };

export default function History() {
  const [tab, setTab] = useState<"conversations" | "mistakes" | "exams" | "activity">("conversations");
  const [convs, setConvs] = useState<Conv[]>([]);
  const [open, setOpen] = useState<ConvFull | null>(null);
  const [mistakes, setMistakes] = useState<Mistake[]>([]);
  const [cat, setCat] = useState("");
  const [attempts, setAttempts] = useState<Attempt[]>([]);
  const [acts, setActs] = useState<Act[]>([]);
  useEffect(() => {
    api.get<Conv[]>("/api/conversation/history").then(setConvs);
    api.get<Attempt[]>("/api/exam/attempts").then(setAttempts);
    api.get<{ history: Act[] }>("/api/analytics").then((a) => setActs(a.history));
  }, []);
  useEffect(() => { api.get<Mistake[]>(`/api/mistakes?limit=200${cat ? `&category=${cat}` : ""}`).then(setMistakes); }, [cat]);

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div><h1 className="h1">Learning History</h1><p className="muted mt-1">Everything you have done, saved automatically: conversations with their corrections, your mistakes to review, exam results and activity.</p></div>
      <div className="flex gap-1">{([["conversations", `Conversations (${convs.length})`], ["mistakes", "Mistakes to review"], ["exams", `Exams (${attempts.length})`], ["activity", "All activity"]] as const).map(([k, l]) =>
        <button key={k} className={tab === k ? "btn-primary" : "btn-ghost"} onClick={() => { setTab(k); setOpen(null); }}>{l}</button>)}</div>

      {tab === "conversations" && !open && (
        <div className="card divide-y divide-ink-100 !p-2 dark:divide-ink-800">
          {convs.length === 0 && <p className="muted p-4">No conversations yet. <Link className="text-brand-500 underline" to="/conversation">Talk to your AI professor</Link>.</p>}
          {convs.map((c) => (
            <button key={c.id} className="flex w-full items-center justify-between px-3 py-3 text-left hover:bg-ink-50 dark:hover:bg-ink-800/50" onClick={() => api.get<ConvFull>(`/api/conversation/${c.id}`).then(setOpen)}>
              <span><b>{c.title}</b><span className="ml-2 text-xs text-ink-400">{when(c.started_at)} · {c.turns} turns</span></span>
              <span className="text-sm text-ink-400">{c.estimated_cefr ? `CEFR ≈ ${c.estimated_cefr}` : c.has_summary ? "reviewed" : ""} →</span>
            </button>
          ))}
        </div>
      )}
      {tab === "conversations" && open && (
        <div className="space-y-3">
          <button className="text-sm text-brand-500" onClick={() => setOpen(null)}>← All conversations</button>
          <h2 className="font-serif text-xl">{open.title} <span className="text-sm text-ink-400">{when(open.started_at)}</span></h2>
          {open.messages.map((m, i) => (
            <div key={i} className={m.role === "user" ? "ml-16" : "mr-16"}>
              <div className={`rounded-2xl px-4 py-2 ${m.role === "user" ? "bg-brand-600 text-white" : "bg-white shadow-sm dark:bg-ink-900"}`}>{m.content}</div>
              {m.feedback && !m.feedback.is_correct && (
                <div className="mt-1 rounded-xl border border-ink-200 p-3 text-sm dark:border-ink-800">
                  <div className="font-medium">{m.feedback.corrected_sentence}</div>
                  {m.feedback.issues.map((x, k) => <p key={k} className="text-ink-600 dark:text-ink-400"><CategoryPill c={x.category} /> {x.original} → {x.corrected}: {x.explanation}</p>)}
                  {m.feedback.advanced_alternative && <p className="text-ink-400">More advanced: {m.feedback.advanced_alternative}</p>}
                </div>
              )}
            </div>
          ))}
          {open.summary && <div className="card text-sm"><div className="label">Session feedback · CEFR ≈ {open.summary.estimated_cefr}</div>
            <ul className="list-disc pl-5">{[...(open.summary.recurring_issues ?? []), ...(open.summary.next_steps ?? [])].map((x: string) => <li key={x}>{x}</li>)}</ul></div>}
        </div>
      )}

      {tab === "mistakes" && (
        <div className="space-y-3">
          <div className="flex gap-1">{["", "grammar", "vocabulary", "naturalness", "pronunciation", "fluency"].map((c) =>
            <button key={c} className={`chip ${cat === c ? "!border-brand-500 text-brand-500" : ""}`} onClick={() => setCat(c)}>{c || "all"}</button>)}</div>
          <div className="card divide-y divide-ink-100 !p-2 dark:divide-ink-800">
            {mistakes.length === 0 && <p className="muted p-4">No mistakes recorded{cat ? " in this category" : ""} yet.</p>}
            {mistakes.map((m, i) => (
              <div key={i} className="px-3 py-2 text-sm">
                <div className="flex items-center gap-2"><CategoryPill c={m.category} /><span className="text-rose-500 line-through">{m.original}</span>→<span className="text-emerald-600 dark:text-emerald-400">{m.corrected}</span></div>
                <div className="text-ink-600 dark:text-ink-400">{m.explanation}</div>
                <div className="text-xs text-ink-400">{when(m.when)} · {m.source.replace(/_/g, " ")}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === "exams" && (
        <div className="card">
          {attempts.length === 0 ? <p className="muted">No exams yet. <Link className="text-brand-500 underline" to="/exams">Take a practice test</Link>.</p> : (
            <table className="w-full text-sm"><tbody>{attempts.map((a) => (
              <tr key={a.id} className="border-t border-ink-100 dark:border-ink-800"><td className="py-2">{when(a.started_at)}</td><td>{EXAM[a.exam_id] ?? a.exam_id}</td>
                <td className="text-ink-400">{a.bands ? Object.entries(a.bands).map(([k, v]) => `${k} ${v}`).join(" · ") : a.finished ? "" : "not finished"}</td>
                <td className="text-right font-serif text-lg">{a.overall_band ?? "–"}</td></tr>))}</tbody></table>)}
          <p className="mt-2 text-xs text-ink-400">Practice estimates, not official scores.</p>
        </div>
      )}

      {tab === "activity" && (
        <div className="card"><table className="w-full text-sm"><tbody>{acts.map((h, i) => (
          <tr key={i} className="border-t border-ink-100 dark:border-ink-800"><td className="py-1.5 text-ink-400">{when(h.when)}</td><td className="capitalize">{h.skill}</td><td className="text-ink-600 dark:text-ink-400">{h.item}</td><td className="text-right">{Math.round(h.score * 100)}%</td></tr>))}</tbody></table>
          {!acts.length && <p className="muted">Your activity will appear here.</p>}</div>
      )}
    </div>
  );
}
