import React, { useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import { HashRouter, MemoryRouter } from "react-router-dom";
import App from "./App";
import { bootPreview, PREVIEW } from "./lib/preview";
import "./index.css";

let theme = "dark";
try { theme = localStorage.getItem("ema-theme") ?? "dark"; } catch { /* storage unavailable */ }
document.documentElement.classList.toggle("dark", theme === "dark");

function PreviewBoot() {
  const [status, setStatus] = useState("Preparing preview…");
  const [ready, setReady] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { bootPreview(setStatus).then(() => setReady(true)).catch((e) => setErr(String(e?.message ?? e))); }, []);
  if (ready) return <MemoryRouter><App /></MemoryRouter>;
  return (
    <div className="grid h-screen place-items-center p-6 text-center">
      <div className="max-w-md space-y-4">
        <div className="font-serif text-3xl text-ink-900 dark:text-white">English Mastery <span className="text-gold-500">AI</span></div>
        {err ? <p className="text-rose-500">The preview could not start: {err}</p> : <>
          <div className="mx-auto h-1.5 w-56 overflow-hidden rounded-full bg-ink-200 dark:bg-ink-800"><div className="h-full w-1/3 animate-pulse rounded-full bg-brand-500" /></div>
          <p className="text-sm text-ink-400">{status}</p>
          <p className="text-xs text-ink-400">The app's real Python engine and database are starting inside your browser. The first visit takes 10–30 seconds; nothing is installed on your computer.</p>
        </>}
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {PREVIEW ? <PreviewBoot /> : <HashRouter><App /></HashRouter>}
  </React.StrictMode>,
);
