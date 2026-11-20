import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, Word } from "../lib/api";
import { useProfile } from "../App";
import { ErrorBox, LevelPill, Speak } from "../components/ui";

interface Due { card_id: number; status: string; word: Word }

const STATUS: Record<string, string> = {
  not_started: "text-ink-400", new: "text-sky-500", learning: "text-amber-500", mastered: "text-emerald-500", often_forgotten: "text-rose-500",
};

export default function Vocabulary() {
  const { profile } = useProfile();
  const [params] = useSearchParams();
  const [tab, setTab] = useState<"review" | "browse">(params.get("domain") ? "browse" : "review");
  const [words, setWords] = useState<Word[]>([]);
  const [due, setDue] = useState<Due[]>([]);
  const [q, setQ] = useState("");
  const [domain, setDomain] = useState(params.get("domain") ?? "");
  const [flipped, setFlipped] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = () => {
    api.get<Word[]>("/api/vocabulary/words").then(setWords).catch((e) => setErr(e.message));
    api.get<Due[]>("/api/vocabulary/review").then(setDue).catch((e) => setErr(e.message));
  };
  useEffect(load, []);

  async function grade(g: number) {
    const c = due[0];
    await api.post(`/api/vocabulary/review/${c.card_id}`, { grade: g });
    setFlipped(false);
    const rest = due.slice(1);
    setDue(g === 0 ? [...rest, c] : rest); // forgotten cards come back this session
  }

  const domains = [...new Set(words.map((w) => w.domain))];
  const shown = words.filter((w) => (!domain || w.domain === domain) && (!q || (w.word + w.definition).toLowerCase().includes(q.toLowerCase())));
  const card = due[0]?.word;
  const accent = profile.accent_preference;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex items-end justify-between">
        <div><h1 className="h1">Vocabulary Masterclass</h1><p className="muted mt-1">Spaced repetition (SM-2) schedules each word right before you'd forget it. Works offline.</p></div>
        <div className="flex gap-1"><button className={tab === "review" ? "btn-primary" : "btn-ghost"} onClick={() => setTab("review")}>Review ({due.length})</button><button className={tab === "browse" ? "btn-primary" : "btn-ghost"} onClick={() => setTab("browse")}>Word bank ({words.length})</button></div>
      </div>
      <ErrorBox msg={err} />

      {tab === "review" && (
        !card ? (
          <div className="card text-center">
            <p className="font-serif text-xl">No cards due right now.</p>
            <p className="muted mt-2">Add words from the word bank, or add the whole starter deck.</p>
            <button className="btn-primary mt-4" onClick={async () => { await api.post("/api/vocabulary/deck-all"); load(); }}>Add all {words.filter((w) => !w.in_deck).length} remaining words</button>
          </div>
        ) : (
          <div className="mx-auto max-w-xl">
            <div className="card min-h-[320px] text-center">
              <div className="flex justify-between text-xs text-ink-400"><span>{card.domain}</span><LevelPill l={card.level} /></div>
              <div className="mt-8 flex items-center justify-center gap-2 font-serif text-4xl">{card.word}<Speak text={card.word} accent={accent} /></div>
              {card.ipa && <div className="mt-2 text-ink-400">{card.ipa}</div>}
              {!flipped ? (
                <button className="btn-ghost mt-10" onClick={() => setFlipped(true)}>Show meaning</button>
              ) : (
                <div className="mt-6 space-y-3 text-left text-sm">
                  <p className="text-base">{card.definition}</p>
                  {card.examples.map((e) => <p key={e} className="flex items-center gap-1 italic">“{e}”<Speak text={e} accent={accent} /></p>)}
                  {card.collocations.length > 0 && <p><span className="label inline">Collocations · </span>{card.collocations.join(" · ")}</p>}
                  {card.synonyms.length > 0 && <p><span className="label inline">Synonyms · </span>{card.synonyms.join(", ")}</p>}
                  {profile.french_explanations && card.french && <p className="text-ink-400">🇫🇷 {card.french}</p>}
                </div>
              )}
            </div>
            {flipped && (
              <div className="mt-4 grid grid-cols-4 gap-2">
                {[["Forgot", 0, "!bg-rose-600"], ["Hard", 1, "!bg-amber-600"], ["Good", 2, ""], ["Easy", 3, "!bg-emerald-600"]].map(([l, g, c]) => (
                  <button key={l as string} className={`btn-primary ${c}`} onClick={() => grade(g as number)}>{l}</button>
                ))}
              </div>
            )}
          </div>
        )
      )}

      {tab === "browse" && (
        <>
          <div className="flex gap-3"><input className="input" placeholder="Search words or definitions…" value={q} onChange={(e) => setQ(e.target.value)} />
            <select className="input !w-56" value={domain} onChange={(e) => setDomain(e.target.value)}><option value="">All domains</option>{domains.map((d) => <option key={d}>{d}</option>)}</select></div>
          <div className="grid grid-cols-2 gap-4">
            {shown.map((w) => (
              <div key={w.id} className="card !p-5">
                <div className="flex items-start justify-between">
                  <div><div className="flex items-center gap-1 font-serif text-lg">{w.word}<Speak text={w.word} accent={accent} /></div><div className="text-xs text-ink-400">{w.ipa} {w.pos}</div></div>
                  <div className="flex items-center gap-2"><span className={`text-xs ${STATUS[w.status ?? "not_started"]}`}>{(w.status ?? "").replace("_", " ")}</span><LevelPill l={w.level} /></div>
                </div>
                <p className="mt-2 text-sm">{w.definition}</p>
                <p className="mt-1 text-sm italic text-ink-600 dark:text-ink-400">“{w.examples[0]}”</p>
                {!w.in_deck && <button className="btn-ghost mt-3 !py-1 text-xs" onClick={async () => { await api.post(`/api/vocabulary/deck/${w.id}`); load(); }}>+ Add to my deck</button>}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
