import { useRef, useState } from "react";
import { api } from "../lib/api";
import { HandsFree } from "../lib/vad";

interface Check { name: string; status: "ok" | "fail" | "skipped"; detail: string; ms?: number }
const ICON = { ok: "✅", fail: "❌", skipped: "⏭" };

/** Live checks of every real service + microphone, so the first real session is a verified one. */
export default function SelfTest() {
  const [busy, setBusy] = useState(false);
  const [checks, setChecks] = useState<Check[] | null>(null);
  const [mic, setMic] = useState<{ state: "idle" | "listening" | "done" | "error"; level: number; heard: boolean; url?: string; msg?: string }>({ state: "idle", level: 0, heard: false });
  const hf = useRef<HandsFree | null>(null);

  async function run() {
    setBusy(true);
    try { setChecks((await api.post<{ results: Check[] }>("/api/system/selftest")).results); } finally { setBusy(false); }
  }

  async function testMic() {
    setMic({ state: "listening", level: 0, heard: false });
    const h = new HandsFree({
      onLevel: (v, speaking) => setMic((m) => ({ ...m, level: v, heard: m.heard || speaking })),
      onUtterance: (blob) => { h.stop(); hf.current = null; setMic((m) => ({ ...m, state: "done", url: URL.createObjectURL(blob) })); },
    });
    try { await h.start(); hf.current = h; setTimeout(() => { if (hf.current === h) { h.stop(); hf.current = null; setMic((m) => (m.state === "listening" ? { ...m, state: "error", msg: "No speech detected in 12 seconds. Check the microphone selected in Windows Sound settings." } : m)); } }, 12000); }
    catch { setMic({ state: "error", level: 0, heard: false, msg: "The browser could not open the microphone. Allow it in Windows Settings › Privacy & security › Microphone, and in the browser's site permissions." }); }
  }

  return (
    <section className="card space-y-4">
      <div className="flex items-center justify-between">
        <div><h2 className="font-semibold">Test my setup</h2><p className="muted">Runs one real request to each service (AI model, correction engine, voice, speech recognition, Azure). Costs a fraction of a cent.</p></div>
        <button className="btn-primary" disabled={busy} onClick={run}>{busy ? "Testing…" : "Run live tests"}</button>
      </div>
      {checks && <table className="w-full text-sm"><tbody>{checks.map((c) => (
        <tr key={c.name} className="border-t border-ink-100 align-top dark:border-ink-800"><td className="w-8 py-2">{ICON[c.status]}</td><td className="w-64 py-2 font-medium">{c.name}</td><td className="py-2 text-ink-600 dark:text-ink-400">{c.detail}{c.ms ? <span className="text-ink-400"> · {c.ms} ms</span> : null}</td></tr>
      ))}</tbody></table>}
      <div className="border-t border-ink-100 pt-4 dark:border-ink-800">
        <div className="flex items-center justify-between">
          <div><h3 className="font-medium">Microphone & hands-free test</h3><p className="muted">Click, say a sentence, then pause. Uses the same voice detection as hands-free conversation.</p></div>
          <button className="btn-ghost" disabled={mic.state === "listening"} onClick={testMic}>{mic.state === "listening" ? "Listening…" : "Test microphone"}</button>
        </div>
        {mic.state === "listening" && <div className="mt-3 h-2 w-full rounded-full bg-ink-100 dark:bg-ink-800"><div className={`h-2 rounded-full ${mic.heard ? "bg-emerald-500" : "bg-ink-400"}`} style={{ width: `${Math.round(mic.level * 100)}%` }} /></div>}
        {mic.state === "done" && <div className="mt-3 flex items-center gap-3 text-sm">✅ Speech detected and recorded. Play it back:<audio controls src={mic.url} className="h-9" /></div>}
        {mic.state === "error" && <p className="mt-3 text-sm text-rose-500">❌ {mic.msg}</p>}
      </div>
    </section>
  );
}
