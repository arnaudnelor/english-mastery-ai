import { useState } from "react";
import { api, Profile } from "../lib/api";
import { ErrorBox } from "../components/ui";

export default function Onboarding({ onDone }: { onDone: (p: Profile) => void }) {
  const [f, setF] = useState({ name: "", estimated_level: "B2", target_level: "C1", daily_minutes: 60, accent_preference: "en-CA", correction_mode: "after_response", french_explanations: true });
  const [err, setErr] = useState<string | null>(null);
  const set = (k: string, v: unknown) => setF({ ...f, [k]: v });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    try { onDone(await api.put<Profile>("/api/profile", f)); } catch (x) { setErr((x as Error).message); }
  }

  return (
    <div className="grid min-h-screen place-items-center p-6">
      <form onSubmit={submit} className="card w-full max-w-lg space-y-4">
        <div>
          <h1 className="h1">Welcome to English Mastery <span className="text-gold-500">AI</span></h1>
          <p className="muted mt-2">A few details so your professor can tailor every lesson. Your profile is stored only on this computer.</p>
        </div>
        <div><label className="label">Your name</label><input className="input" required value={f.name} onChange={(e) => set("name", e.target.value)} /></div>
        <div className="grid grid-cols-2 gap-4">
          <div><label className="label">Current level (estimate)</label>
            <select className="input" value={f.estimated_level} onChange={(e) => set("estimated_level", e.target.value)}>{["B1", "B2", "C1"].map((l) => <option key={l}>{l}</option>)}</select></div>
          <div><label className="label">Target level</label>
            <select className="input" value={f.target_level} onChange={(e) => set("target_level", e.target.value)}>{["B2", "C1", "C2"].map((l) => <option key={l}>{l}</option>)}</select></div>
          <div><label className="label">Daily study</label>
            <select className="input" value={f.daily_minutes} onChange={(e) => set("daily_minutes", +e.target.value)}>{[30, 60, 90, 120, 180].map((m) => <option key={m} value={m}>{m} min</option>)}</select></div>
          <div><label className="label">Accent</label>
            <select className="input" value={f.accent_preference} onChange={(e) => set("accent_preference", e.target.value)}>
              <option value="en-CA">Canadian</option><option value="en-US">American</option><option value="en-GB">British</option></select></div>
        </div>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.french_explanations} onChange={(e) => set("french_explanations", e.target.checked)} /> Add French explanations when helpful</label>
        <ErrorBox msg={err} />
        <button className="btn-primary w-full">Start learning</button>
        <p className="text-xs text-ink-400">A full four-skill placement test arrives in Phase 8; until then the app refines your level from your results.</p>
      </form>
    </div>
  );
}
