import { useState } from "react";
import { api } from "../lib/api";
import { ErrorBox } from "../components/ui";

export default function PinScreen({ onUnlocked }: { onUnlocked: () => void }) {
  const [pin, setPin] = useState("");
  const [err, setErr] = useState<string | null>(null);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    try { await api.post("/api/system/unlock", { pin }); onUnlocked(); } catch { setErr("Wrong PIN. It is shown in the window that start-lan.bat opened on your computer."); }
  }
  return (
    <div className="grid min-h-screen place-items-center p-6">
      <form onSubmit={submit} className="card w-full max-w-sm space-y-4 text-center">
        <h1 className="font-serif text-2xl">English Mastery <span className="text-gold-500">AI</span></h1>
        <p className="muted">You're connecting from another device. Enter the PIN shown on your computer.</p>
        <input className="input text-center text-2xl tracking-[0.5em]" inputMode="numeric" autoFocus value={pin} onChange={(e) => setPin(e.target.value)} />
        <ErrorBox msg={err} />
        <button className="btn-primary w-full" disabled={pin.length < 4}>Unlock</button>
      </form>
    </div>
  );
}
