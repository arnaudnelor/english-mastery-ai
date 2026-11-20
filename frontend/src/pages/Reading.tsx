import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../lib/api";
import { useProfile } from "../App";
import { CategoryPill, ErrorBox, LevelPill, Speak } from "../components/ui";
import { BookmarkButton } from "../components/Bookmark";

interface TextSummary { id: string; title: string; level: string; genre: string; domain: string; word_count: number; question_count: number }
interface Question { id: string; type: string; prompt: string; options: string[] }
interface Text extends TextSummary { body: string; glossary: Record<string, string>; questions: Question[]; discussion: string }
interface QResult { correct: boolean; answer: string; explanation: string }
interface Definition { word: string; ipa: string; part_of_speech: string; meaning_in_context: string; other_common_meaning: string | null; example: string; french: string | null }
interface SummaryResult {
  content_score: number; language_score: number; captured_main_idea: boolean; missing_points: string[]; inaccuracies: string[];
  copied_phrases: string[]; corrections: { original: string; corrected: string; explanation: string; category: string }[]; model_summary: string; comment: string;
}

export function ReadingList() {
  const [texts, setTexts] = useState<TextSummary[]>([]);
  const [level, setLevel] = useState("");
  useEffect(() => { api.get<TextSummary[]>("/api/reading/texts").then(setTexts); }, []);
  const shown = texts.filter((t) => !level || t.level === level);
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex items-end justify-between">
        <div><h1 className="h1">Advanced Reading</h1><p className="muted mt-1">Original texts from B2 to C2: news, finance, research, fiction and essays. Timed, with comprehension, inference and argument questions.</p></div>
        <div className="flex gap-1">{["", "A1", "A2", "B1", "B2", "C1", "C2"].map((l) => <button key={l} onClick={() => setLevel(l)} className={level === l ? "btn-primary" : "btn-ghost"}>{l || "All"}</button>)}</div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        {shown.map((t) => (
          <Link key={t.id} to={`/reading/${t.id}`} className="card transition hover:border-brand-400">
            <div className="flex items-center justify-between"><span className="text-xs uppercase tracking-wide text-ink-400">{t.genre}</span><LevelPill l={t.level} /></div>
            <div className="mt-2 font-serif text-lg">{t.title}</div>
            <div className="mt-3 text-xs text-ink-400">{t.word_count} words · {t.question_count} questions · about {Math.ceil(t.word_count / 200)} min</div>
          </Link>
        ))}
      </div>
    </div>
  );
}

function escapeRe(s: string) { return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }

export function ReadingText() {
  const { id } = useParams();
  const { profile } = useProfile();
  const [t, setT] = useState<Text | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [popup, setPopup] = useState<{ word: string; text?: string; def?: Definition; loading?: boolean; error?: string } | null>(null);
  const [speed, setSpeed] = useState<{ wpm: number; benchmark_wpm: number; note: string } | null>(null);
  const [answers, setAnswers] = useState<Record<string, QResult & { chosen: string }>>({});
  const [summary, setSummary] = useState("");
  const [sres, setSres] = useState<SummaryResult | null>(null);
  const [sbusy, setSbusy] = useState(false);
  const started = useRef(Date.now());

  useEffect(() => { api.get<Text>(`/api/reading/texts/${id}`).then((x) => { setT(x); started.current = Date.now(); }).catch((e) => setErr(e.message)); }, [id]);

  const glossRe = useMemo(() => {
    if (!t) return null;
    const keys = Object.keys(t.glossary).sort((a, b) => b.length - a.length).map(escapeRe);
    return new RegExp(`\\b(${keys.join("|")})\\b`, "gi");
  }, [t]);

  if (err) return <ErrorBox msg={err} />;
  if (!t) return <div className="text-ink-400">Loading…</div>;

  const glossFor = (w: string) => Object.entries(t.glossary).find(([k]) => k.toLowerCase() === w.toLowerCase())?.[1];

  function renderPara(p: string, i: number) {
    const parts = glossRe ? p.split(glossRe) : [p];
    return (
      <p key={i} onDoubleClick={(e) => defineSelection(e.currentTarget.textContent ?? "")}>
        {parts.map((part, k) => glossFor(part)
          ? <button key={k} type="button" onClick={() => setPopup({ word: part, text: glossFor(part) })} className="rounded bg-gold-400/15 px-0.5 text-inherit underline decoration-gold-500 decoration-dotted underline-offset-4">{part}</button>
          : <Fragment key={k}>{part}</Fragment>)}
      </p>
    );
  }

  async function defineSelection(para: string) {
    const word = window.getSelection()?.toString().trim().replace(/[^A-Za-z'-]/g, "");
    if (!word || word.length < 2) return;
    const g = glossFor(word);
    if (g) return setPopup({ word, text: g });
    const sentence = para.split(/(?<=[.!?])\s+/).find((s) => s.toLowerCase().includes(word.toLowerCase())) ?? "";
    setPopup({ word, loading: true });
    try { setPopup({ word, def: await api.post<Definition>("/api/reading/define", { word, sentence }) }); }
    catch (e) { setPopup({ word, error: (e as ApiError).status === 412 ? "Explaining any word needs an AI key (Settings). Highlighted words work offline." : (e as Error).message }); }
  }

  async function finish() {
    const seconds = Math.max(1, Math.round((Date.now() - started.current) / 1000));
    setSpeed(await api.post(`/api/reading/texts/${id}/finish`, { seconds }));
  }

  async function answer(q: Question, chosen: string) {
    const r = await api.post<QResult>(`/api/reading/texts/${id}/answer`, { question_id: q.id, answer: chosen });
    setAnswers((a) => ({ ...a, [q.id]: { ...r, chosen } }));
  }

  async function submitSummary() {
    setSbusy(true); setErr(null);
    try { setSres(await api.post<SummaryResult>(`/api/reading/texts/${id}/summary`, { summary })); }
    catch (e) { setErr((e as Error).message); } finally { setSbusy(false); }
  }

  const done = Object.keys(answers).length;
  const score = Object.values(answers).filter((a) => a.correct).length;

  return (
    <div className="mx-auto grid max-w-6xl grid-cols-[1fr_320px] gap-6">
      <div className="space-y-6">
        <Link to="/reading" className="text-sm text-brand-500">← All texts</Link>
        <article className="card">
          <div className="flex items-center gap-2"><LevelPill l={t.level} /><span className="text-xs uppercase text-ink-400">{t.genre} · {t.word_count} words</span></div>
          <div className="mt-3 flex items-start justify-between gap-3"><h1 className="h1">{t.title}</h1><BookmarkButton kind="reading" itemId={t.id} title={t.title} route={`/reading/${t.id}`} /></div>
          <div className="mt-6 space-y-4 font-serif text-[17px] leading-8">{t.body.split("\n\n").map(renderPara)}</div>
          <div className="mt-6 flex items-center justify-between border-t border-ink-100 pt-4 dark:border-ink-800">
            <span className="text-xs text-ink-400">Tap a highlighted word for its meaning. Double-click any other word for an AI explanation in context.</span>
            {!speed ? <button className="btn-primary" onClick={finish}>I've finished reading</button>
              : <span className="text-sm"><b>{speed.wpm} wpm</b> <span className="text-ink-400">(benchmark ≈ {speed.benchmark_wpm})</span></span>}
          </div>
        </article>

        {speed && (
          <div className="card space-y-5">
            <div className="flex items-center justify-between"><h2 className="font-semibold">Comprehension</h2>{done > 0 && <span className="text-sm text-ink-400">{score}/{done}</span>}</div>
            {t.questions.map((q, n) => {
              const a = answers[q.id];
              return (
                <div key={q.id}>
                  <div className="mb-2 text-sm"><span className="pill mr-2 bg-ink-100 capitalize text-ink-600 dark:bg-ink-800 dark:text-ink-400">{q.type.replace("_", " ")}</span>{n + 1}. {q.prompt}</div>
                  <div className="grid gap-2">{q.options.map((o) => (
                    <button key={o} disabled={!!a} onClick={() => answer(q, o)}
                      className={`btn-ghost !justify-start text-left ${a && o === a.answer ? "!border-emerald-500 !bg-emerald-50 dark:!bg-emerald-500/10" : a && o === a.chosen ? "!border-rose-500 !bg-rose-50 dark:!bg-rose-500/10" : ""}`}>{o}</button>
                  ))}</div>
                  {a && <p className="mt-2 text-sm text-ink-600 dark:text-ink-400">{a.correct ? "✓ " : "✗ "}{a.explanation}</p>}
                </div>
              );
            })}
          </div>
        )}

        {speed && (
          <div className="card space-y-3">
            <h2 className="font-semibold">Summarise in your own words</h2>
            <p className="muted">Aim for 60–100 words. Paraphrase rather than copying phrases from the text.</p>
            <textarea className="input min-h-[140px] font-serif" value={summary} onChange={(e) => setSummary(e.target.value)} />
            <div className="flex justify-between"><span className="text-xs text-ink-400">{summary.trim() ? summary.trim().split(/\s+/).length : 0} words · needs an AI key</span>
              <button className="btn-primary" disabled={sbusy || summary.trim().split(/\s+/).length < 15} onClick={submitSummary}>{sbusy ? "Assessing…" : "Get feedback"}</button></div>
            <ErrorBox msg={err} />
            {sres && (
              <div className="space-y-3 text-sm">
                <div className="flex gap-4"><span>Content <b>{Math.round(sres.content_score * 100)}%</b></span><span>Language <b>{Math.round(sres.language_score * 100)}%</b></span><span>{sres.captured_main_idea ? "✓ Main idea captured" : "✗ Main idea missing"}</span></div>
                <p>{sres.comment}</p>
                {sres.missing_points.length > 0 && <div><div className="label">Missing points</div><ul className="list-disc pl-5">{sres.missing_points.map((m) => <li key={m}>{m}</li>)}</ul></div>}
                {sres.copied_phrases.length > 0 && <div><div className="label">Copied from the text — paraphrase these</div><ul className="list-disc pl-5">{sres.copied_phrases.map((m) => <li key={m}>“{m}”</li>)}</ul></div>}
                {sres.corrections.map((c, k) => <div key={k} className="border-l-2 border-ink-200 pl-3 dark:border-ink-800"><CategoryPill c={c.category} /> <span className="text-rose-500 line-through">{c.original}</span> → <span className="text-emerald-600">{c.corrected}</span><p className="text-ink-400">{c.explanation}</p></div>)}
                <div><div className="label">Model summary</div><p className="rounded-xl bg-ink-50 p-3 font-serif dark:bg-ink-950">{sres.model_summary}</p></div>
              </div>
            )}
          </div>
        )}
        {speed && <div className="card"><div className="label">Speaking follow-up</div><p>{t.discussion}</p><Link to="/conversation" className="btn-ghost mt-3">Discuss it with your AI professor</Link></div>}
      </div>

      <aside className="space-y-4">
        <div className="card sticky top-0">
          <h2 className="mb-3 font-semibold">Word helper</h2>
          {!popup ? <p className="muted">Select a highlighted or double-clicked word to see it here.</p> : (
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-1 font-serif text-xl">{popup.def?.word ?? popup.word}<Speak text={popup.word} accent={profile.accent_preference} /></div>
              {popup.text && <p>{popup.text}</p>}
              {popup.loading && <p className="text-ink-400">Looking it up…</p>}
              {popup.error && <p className="text-rose-500">{popup.error}</p>}
              {popup.def && (<>
                <p className="text-ink-400">{popup.def.ipa} · {popup.def.part_of_speech}</p>
                <p><b>Here:</b> {popup.def.meaning_in_context}</p>
                {popup.def.other_common_meaning && <p><b>Also:</b> {popup.def.other_common_meaning}</p>}
                <p className="italic">“{popup.def.example}”</p>
                {popup.def.french && <p className="text-ink-400">🇫🇷 {popup.def.french}</p>}
              </>)}
            </div>
          )}
          <div className="mt-5 border-t border-ink-100 pt-3 dark:border-ink-800">
            <div className="label">Glossary</div>
            <ul className="space-y-1 text-sm">{Object.entries(t.glossary).map(([k, v]) => <li key={k}><b>{k}</b> <span className="text-ink-400">— {v}</span></li>)}</ul>
          </div>
        </div>
      </aside>
    </div>
  );
}
