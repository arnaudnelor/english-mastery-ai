import { createContext, useContext, useEffect, useState } from "react";
import { NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { api, ApiError, Profile } from "./lib/api";
import PinScreen from "./pages/PinScreen";
import Dashboard from "./pages/Dashboard";
import Conversation from "./pages/Conversation";
import { GrammarList, GrammarTopic } from "./pages/Grammar";
import Vocabulary from "./pages/Vocabulary";
import Writing from "./pages/Writing";
import Settings from "./pages/Settings";
import Onboarding from "./pages/Onboarding";
import { ReadingList, ReadingText } from "./pages/Reading";
import { ListeningItem, ListeningList } from "./pages/Listening";
import Pronunciation from "./pages/Pronunciation";
import ExamPage from "./pages/Exam";
import Path from "./pages/Path";
import Tests from "./pages/Tests";
import Analytics from "./pages/Analytics";
import Search from "./pages/Search";
import History from "./pages/History";
import { useReminder } from "./lib/reminder";
import { PREVIEW } from "./lib/preview";
import { Assessments, BusinessAcademy, BusinessCategory, LevelPage, Overview } from "./pages/Academy";
import { AnimatedScene, VideoHub, VideoPlayerPage } from "./pages/Video";

interface Ctx { profile: Profile; setProfile: (p: Profile) => void }
const ProfileCtx = createContext<Ctx>(null!);
export const useProfile = () => useContext(ProfileCtx);
interface AcademyCtxT { overview: Overview | null; reload: () => void }
const AcademyCtx = createContext<AcademyCtxT>({ overview: null, reload: () => {} });
export const useAcademy = () => useContext(AcademyCtx);

const ACADEMY_NAV: { to: string; label: string }[] = [
  { to: "/", label: "Dashboard" },
  { to: "/path", label: "My Learning Path" },
  { to: "/tests?start=placement", label: "Placement Test" },
];

const NAV: { to: string; label: string; phase?: number }[] = [
  { to: "/conversation", label: "AI Conversation" },
  { to: "/listening", label: "Listening Laboratory" },
  { to: "/video", label: "Video Academy" },
  { to: "/grammar", label: "Grammar Academy" },
  { to: "/vocabulary", label: "Vocabulary" },
  { to: "/pronunciation", label: "Pronunciation" },
  { to: "/reading", label: "Reading" },
  { to: "/writing", label: "Writing" },
  { to: "/exams", label: "IELTS & TOEFL" },
  { to: "/tests", label: "Tests & Assessments" },
  { to: "/assessments", label: "Assessment Results" },
  { to: "/analytics", label: "Progress Analytics" },
  { to: "/history", label: "Learning History" },
  { to: "/settings", label: "Settings" },
];

export default function App() {
  const [profile, setProfile] = useState<Profile | null | undefined>(undefined);
  const [err, setErr] = useState<string | null>(null);
  const [locked, setLocked] = useState(false);
  const [q, setQ] = useState("");
  const navigate = useNavigate();
  const location = useLocation();
  const [overview, setOverview] = useState<Overview | null>(null);
  const reload = () => { api.get<Overview>("/api/academy/overview").then(setOverview).catch(() => {}); };
  useEffect(() => { if (profile) reload(); }, [profile, location.pathname]); // eslint-disable-line
  useReminder(profile?.reminder_time);

  const load = () => api.get<Profile | null>("/api/profile").then((p) => { setLocked(false); setProfile(p); })
    .catch((e: ApiError) => (e.status === 401 ? setLocked(true) : setErr(e.message)));
  useEffect(() => { load(); }, []);

  if (locked) return <PinScreen onUnlocked={load} />;
  if (err) return <div className="p-10 text-rose-500">{err}</div>;
  if (profile === undefined) return <div className="grid h-screen place-items-center text-ink-400">Starting your academy…</div>;
  if (profile === null) return <Onboarding onDone={setProfile} />;

  return (
    <ProfileCtx.Provider value={{ profile, setProfile }}>
     <AcademyCtx.Provider value={{ overview, reload }}>
      <div className="flex h-screen overflow-hidden">
        <aside className="flex w-64 shrink-0 flex-col border-r border-ink-200/70 bg-white dark:border-ink-800 dark:bg-ink-900">
          <div className="px-6 pb-4 pt-6">
            <div className="font-serif text-xl leading-tight">English Mastery <span className="text-gold-500">AI</span></div>
            <div className="mt-1 text-xs text-ink-400">Your Personal Intelligent English Academy</div>
          </div>
          <form className="px-4 pb-3" onSubmit={(e) => { e.preventDefault(); if (q.trim().length > 1) navigate(`/search?q=${encodeURIComponent(q.trim())}`); }}>
            <input className="input !py-1.5" placeholder="Search lessons, words…" value={q} onChange={(e) => setQ(e.target.value)} />
          </form>
          <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 pb-4">
            <div className="px-3 pb-1 pt-1 text-[10px] font-semibold uppercase tracking-widest text-ink-400">Academy</div>
            {ACADEMY_NAV.map((n) => <SideLink key={n.to} to={n.to} label={n.label} />)}
            {(overview?.levels ?? []).map((lv) => (
              <SideLink key={lv.code} to={`/level/${lv.code}`} label={`${lv.code} · ${lv.name}`}
                right={lv.status === "locked" ? "🔒" : lv.status === "completed" ? "✓" : lv.status === "current" ? `${lv.percent}%` : ""} />
            ))}
            <SideLink to="/business" label="Business English Academy" />
            <div className="px-3 pb-1 pt-4 text-[10px] font-semibold uppercase tracking-widest text-ink-400">Practice tools</div>
            {NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.to === "/"}
                className={({ isActive }) =>
                  `flex items-center justify-between rounded-lg px-3 py-2 text-sm transition ${
                    isActive ? "bg-brand-50 font-medium text-brand-700 dark:bg-brand-500/15 dark:text-brand-100"
                    : n.phase ? "text-ink-400 hover:bg-ink-50 dark:hover:bg-ink-800/50"
                    : "text-ink-800 hover:bg-ink-50 dark:text-ink-200 dark:hover:bg-ink-800/50"}`
                }
              >
                {n.label}
                {n.phase && <span className="text-[10px] uppercase tracking-wide text-gold-500">Soon</span>}
              </NavLink>
            ))}
          </nav>
          <div className="border-t border-ink-200/70 px-6 py-4 text-xs text-ink-400 dark:border-ink-800">
            {profile.name} · target {profile.target_level}
          </div>
        </aside>
        <main className="flex-1 overflow-y-auto p-8">
          {PREVIEW && (
            <div className="mx-auto mb-6 max-w-6xl rounded-xl border border-gold-500/50 bg-gold-400/10 px-4 py-2 text-sm text-ink-800 dark:text-ink-100">
              <b>Web edition</b>: runs in your browser and saves your progress on this device automatically. Every lesson, exercise, exam, video scene and statistic works now. To switch on your AI professor (conversation, corrections, marking), open <b>Settings</b> and follow the free 2-minute setup.
            </div>
          )}
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/conversation" element={<Conversation />} />
            <Route path="/grammar" element={<GrammarList />} />
            <Route path="/grammar/:id" element={<GrammarTopic />} />
            <Route path="/vocabulary" element={<Vocabulary />} />
            <Route path="/writing" element={<Writing />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/reading" element={<ReadingList />} />
            <Route path="/reading/:id" element={<ReadingText />} />
            <Route path="/listening" element={<ListeningList />} />
            <Route path="/listening/:id" element={<ListeningItem />} />
            <Route path="/pronunciation" element={<Pronunciation />} />
            <Route path="/path" element={<Path />} />
            <Route path="/video" element={<VideoHub />} />
            <Route path="/video/scene/:id" element={<AnimatedScene />} />
            <Route path="/video/:id" element={<VideoPlayerPage />} />
            <Route path="/exams" element={<ExamPage />} />
            <Route path="/business" element={<BusinessAcademy />} />
            <Route path="/business/:id" element={<BusinessCategory />} />
            <Route path="/level/:code" element={<LevelPage />} />
            <Route path="/lesson/:id" element={<GrammarTopic />} />
            <Route path="/assessments" element={<Assessments />} />
            <Route path="/tests" element={<Tests />} />
            <Route path="/search" element={<Search />} />
            <Route path="/history" element={<History />} />
            <Route path="/analytics" element={<Analytics />} />
          </Routes>
        </main>
      </div>
     </AcademyCtx.Provider>
    </ProfileCtx.Provider>
  );
}

function SideLink({ to, label, right }: { to: string; label: string; right?: string }) {
  const loc = useLocation();
  const [path, qs] = to.split("?");
  const active = qs ? loc.pathname === path && loc.search.includes(qs) : path === "/" ? loc.pathname === "/" : loc.pathname === path || loc.pathname.startsWith(path + "/");
  return (
    <NavLink to={to} className={`flex items-center justify-between rounded-lg px-3 py-2 text-sm transition ${active ? "bg-brand-50 font-medium text-brand-700 dark:bg-brand-500/15 dark:text-brand-100" : "text-ink-800 hover:bg-ink-50 dark:text-ink-200 dark:hover:bg-ink-800/50"}`}>
      {label}{right && <span className="text-[11px] text-ink-400">{right}</span>}
    </NavLink>
  );
}
