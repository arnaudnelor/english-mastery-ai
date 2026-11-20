import { Link } from "react-router-dom";

const TRACKS = [
  { title: "Corporate finance & investment", icon: "📈", domains: ["finance", "investment"], modes: [["investment_committee", "Investment committee"], ["analyst_meeting", "Analyst meeting"], ["finance", "Client conversation"]], reading: ["central-banks-inflation", "esg-quarterly-report"], listening: ["lecture-behavioural-finance"], writing: ["report", "proposal"] },
  { title: "Banking & risk management", icon: "🏦", domains: ["banking", "risk management"], modes: [["finance", "Banking discussion"], ["negotiation", "Negotiation"]], reading: ["central-banks-inflation"], listening: ["news-housing"], writing: ["email", "report"] },
  { title: "Economics", icon: "🌐", domains: ["economics"], modes: [["debate", "Policy debate"], ["university", "Economics seminar"]], reading: ["central-banks-inflation"], listening: ["news-housing"], writing: ["essay"] },
  { title: "AI, data & technology", icon: "🤖", domains: ["technology"], modes: [["debate", "AI debate"], ["presentation", "Tech presentation"]], reading: ["algorithmic-hiring"], listening: ["podcast-ai-work"], writing: ["report", "essay"] },
  { title: "Project management & leadership", icon: "🧭", domains: ["project management", "management", "leadership"], modes: [["business", "Status meeting"], ["negotiation", "Stakeholder negotiation"], ["mba", "MBA case"]], reading: ["four-day-week"], listening: ["budget-meeting"], writing: ["minutes", "email", "proposal"] },
  { title: "Academic research & graduate study", icon: "🎓", domains: ["academic"], modes: [["phd_interview", "PhD interview"], ["university", "Seminar"], ["academic", "Research discussion"]], reading: ["sleep-memory-research", "translation-and-power"], listening: ["lecture-behavioural-finance"], writing: ["essay", "summary"] },
  { title: "Careers & networking", icon: "🤝", domains: ["business"], modes: [["job_interview", "Job interview"], ["networking", "Networking event"]], reading: [], listening: ["job-interview-analyst", "coffee-shop-catchup"], writing: ["cover_letter", "email"] },
];

export default function Business() {
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div><h1 className="h1">Business, Finance & Academic English</h1><p className="muted mt-1">Specialised tracks that bring together vocabulary, role-plays with your AI professor, readings, recordings and writing tasks for each field.</p></div>
      <div className="grid grid-cols-2 gap-5">{TRACKS.map((t) => (
        <div key={t.title} className="card space-y-3">
          <div className="flex items-center gap-3"><span className="text-3xl">{t.icon}</span><h2 className="font-serif text-xl">{t.title}</h2></div>
          <Row label="Vocabulary">{t.domains.map((d) => <Link key={d} className="chip" to={`/vocabulary?domain=${encodeURIComponent(d)}`}>{d}</Link>)}</Row>
          <Row label="Role-plays">{t.modes.map(([m, l]) => <Link key={m + l} className="chip" to={`/conversation?mode=${m}`}>🎙 {l}</Link>)}</Row>
          {t.reading.length > 0 && <Row label="Reading">{t.reading.map((r) => <Link key={r} className="chip" to={`/reading/${r}`}>{r.replace(/-/g, " ")}</Link>)}</Row>}
          <Row label="Listening">{t.listening.map((r) => <Link key={r} className="chip" to={`/listening/${r}`}>{r.replace(/-/g, " ")}</Link>)}</Row>
          <Row label="Writing">{t.writing.map((w) => <Link key={w} className="chip" to={`/writing?genre=${w}`}>{w.replace(/_/g, " ")}</Link>)}</Row>
        </div>
      ))}</div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="flex flex-wrap items-center gap-1.5"><span className="label !mb-0 w-24">{label}</span>{children}</div>;
}
