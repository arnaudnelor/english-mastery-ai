import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../lib/api";
import { useProfile } from "../App";
import { ErrorBox, LevelPill, Speak } from "../components/ui";
import { BookmarkButton } from "../components/Bookmark";

interface TopicSummary { id: string; title: string; level: string; unit: string; summary: string; exercise_count: number }
interface Exercise { id: string; type: "mcq" | "gap" | "correct" | "translate"; prompt: string; options?: string[] }
interface Topic extends TopicSummary { explanation: string; explanation_fr?: string; examples: { en: string; note: string }[]; exercises: Exercise[] }
interface Result { correct: boolean; accepted_answers: string[]; explanation: string }

export function GrammarList() {
  const [topics, setTopics] = useState<TopicSummary[]>([]);
  const [level, setLevel] = useState<string>("");
  useEffect(() => { api.get<TopicSummary[]>("/api/grammar/topics").then(setTopics); }, []);
  const shown = topics.filter((t) => !level || t.level === level);
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex items-end justify-between">
        <div><h1 className="h1">Grammar Academy</h1><p className="muted mt-1">20 topics from B2 to C2, written for French speakers, with exercises that feed your weakness tracker. Works offline.</p></div>
        <div className="flex gap-1">{["", "B2", "C1", "C2"].map((l) => <button key={l} onClick={() => setLevel(l)} className={level === l ? "btn-primary" : "btn-ghost"}>{l || "All"}</button>)}</div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        {shown.map((t) => (
          <Link key={t.id} to={`/grammar/${t.id}`} className="card transition hover:border-brand-400">
            <div className="flex items-center justify-between"><span className="text-xs uppercase tracking-wide text-ink-400">{t.unit}</span><LevelPill l={t.level} /></div>
            <div className="mt-2 font-serif text-lg">{t.title}</div>
            <p className="muted mt-1">{t.summary}</p>
            <div className="mt-3 text-xs text-ink-400">{t.exercise_count} exercises</div>
          </Link>
        ))}
        {shown.length === 0 && <p className="muted">No topics at this level yet.</p>}
      </div>
    </div>
  );
}

export function GrammarTopic() {
  const { id } = useParams();
  const { profile } = useProfile();
  const [t, setT] = useState<Topic | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [results, setResults] = useState<Record<string, Result>>({});
  const [err, setErr] = useState<string | null>(null);
  const [startedAt] = useState(Date.now());
  useEffect(() => { api.get<Topic>(`/api/grammar/topics/${id}`).then(setT).catch((e) => setErr(e.message)); }, [id]);

  async function check(ex: Exercise, value?: string) {
    const answer = value ?? answers[ex.id] ?? "";
    if (!answer.trim()) return;
    try {
      const r = await api.post<Result>(`/api/grammar/topics/${id}/answer`, { exercise_id: ex.id, answer, seconds: Math.min(600, Math.round((Date.now() - startedAt) / 1000 / Math.max(1, t!.exercises.length))) });
      setResults((x) => ({ ...x, [ex.id]: r }));
    } catch (e) { setErr((e as Error).message); }
  }

  if (err) return <ErrorBox msg={err} />;
  if (!t) return <div className="text-ink-400">Loading…</div>;
  const done = Object.keys(results).length;
  const score = Object.values(results).filter((r) => r.correct).length;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Link to="/grammar" className="text-sm text-brand-500">← All topics</Link>
      <div><div className="flex items-center gap-2"><LevelPill l={t.level} /><span className="text-xs uppercase text-ink-400">{t.unit}</span></div><div className="mt-2 flex items-center justify-between"><h1 className="h1">{t.title}</h1><BookmarkButton kind="grammar" itemId={t.id} title={t.title} route={`/grammar/${t.id}`} /></div></div>
      <div className="card space-y-3 leading-relaxed">
        {t.explanation.split("\n").filter(Boolean).map((p, i) => <p key={i}>{p}</p>)}
        {profile.french_explanations && t.explanation_fr && <p className="rounded-xl bg-ink-50 p-3 italic text-ink-600 dark:bg-ink-950 dark:text-ink-400">🇫🇷 {t.explanation_fr}</p>}
      </div>
      <div className="card">
        <h2 className="mb-3 font-semibold">Examples in context</h2>
        <ul className="space-y-3">{t.examples.map((e) => (
          <li key={e.en}><div className="flex items-center gap-1 font-medium">{e.en}<Speak text={e.en} accent={profile.accent_preference} /></div><div className="text-sm text-ink-400">{e.note}</div></li>
        ))}</ul>
      </div>
      <div className="card space-y-5">
        <div className="flex items-center justify-between"><h2 className="font-semibold">Practice</h2>{done > 0 && <span className="text-sm text-ink-400">{score}/{done} correct</span>}</div>
        {t.exercises.map((ex, n) => {
          const r = results[ex.id];
          return (
            <div key={ex.id} className="border-t border-ink-100 pt-4 first:border-0 first:pt-0 dark:border-ink-800">
              <div className="mb-2 text-sm"><span className="text-ink-400">{n + 1}. {ex.type === "correct" ? "Correct the sentence:" : ex.type === "gap" ? "Fill the gap:" : ex.type === "translate" ? "Write:" : ""}</span> <span className="font-medium">{ex.prompt}</span></div>
              {ex.type === "mcq" ? (
                <div className="flex flex-wrap gap-2">{ex.options!.map((o) => (
                  <button key={o} disabled={!!r} onClick={() => { setAnswers((a) => ({ ...a, [ex.id]: o })); check(ex, o); }}
                    className={`btn-ghost ${r && answers[ex.id] === o ? (r.correct ? "!border-emerald-500 !bg-emerald-50 dark:!bg-emerald-500/10" : "!border-rose-500 !bg-rose-50 dark:!bg-rose-500/10") : ""}`}>{o}</button>
                ))}</div>
              ) : (
                <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); check(ex); }}>
                  <input className="input" disabled={!!r} value={answers[ex.id] ?? ""} onChange={(e) => setAnswers((a) => ({ ...a, [ex.id]: e.target.value }))} />
                  <button className="btn-primary" disabled={!!r}>Check</button>
                </form>
              )}
              {r && (
                <div className={`mt-2 rounded-xl p-3 text-sm ${r.correct ? "bg-emerald-50 text-emerald-800 dark:bg-emerald-500/10 dark:text-emerald-300" : "bg-rose-50 text-rose-800 dark:bg-rose-500/10 dark:text-rose-200"}`}>
                  <b>{r.correct ? "Correct." : "Not quite."}</b> {!r.correct && <>Answer: <i>{r.accepted_answers[0]}</i>. </>}{r.explanation}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
