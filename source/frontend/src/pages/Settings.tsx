import { useEffect, useState } from "react";
import { api, Feature, Profile } from "../lib/api";
import { useProfile } from "../App";
import { ErrorBox } from "../components/ui";
import SelfTest from "../components/SelfTest";
import { PREVIEW } from "../lib/preview";
import { englishVoices, getVoicePrefs, resetVoiceDetection, setVoicePrefs, speakLocal, voiceGender, VoicePrefs } from "../lib/speech";

interface Providers { llm_provider: string; llm_model: string; stt: string; tts: string; keys: Record<string, boolean>; azure_speech_region: string }

const NEEDS: Record<string, string> = { llm_key: "AI professor (free Gemini key)", openai_key: "OpenAI key", azure_key: "Azure Speech key + region", internet: "internet", microphone: "microphone" };

export default function Settings() {
  const { profile, setProfile } = useProfile();
  const [p, setP] = useState<Profile>(profile);
  const [prov, setProv] = useState<Providers | null>(null);
  const [features, setFeatures] = useState<Feature[]>([]);
  const [keyInput, setKeyInput] = useState({ provider: "gemini", api_key: "" });
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [dark, setDark] = useState(document.documentElement.classList.contains("dark"));

  const [local, setLocal] = useState(true);
  useEffect(() => { api.get<{ local: boolean }>("/api/system/whoami").then((w) => setLocal(w.local)); }, []);
  const load = () => { api.get<Providers>("/api/system/providers").then(setProv); api.get<Feature[]>("/api/system/features").then(setFeatures); };
  useEffect(load, []);

  const ok = (m: string) => { setErr(null); setMsg(m); setTimeout(() => setMsg(null), 2500); };
  const fail = (e: unknown) => setErr((e as Error).message);

  async function saveProfile() { try { const r = await api.put<Profile>("/api/profile", p); setProfile(r); ok("Profile saved."); } catch (e) { fail(e); } }
  async function saveKey() {
    try {
      await api.post("/api/system/keys", { ...keyInput, api_key: keyInput.api_key.trim() });
      // The AI professor uses the provider whose key was just added
      if (["gemini", "openai", "anthropic"].includes(keyInput.provider) && prov) {
        const model = { gemini: "gemini-2.5-flash", openai: "gpt-4o-mini", anthropic: "claude-sonnet-5-5" }[keyInput.provider as "gemini"];
        await api.put("/api/system/providers", { llm_provider: keyInput.provider, llm_model: model, azure_speech_region: prov.azure_speech_region });
      }
      resetVoiceDetection();
      setKeyInput({ ...keyInput, api_key: "" }); load();
      ok(PREVIEW ? "Key saved in this browser. Now click “Run live tests” above." : "Key stored in Windows Credential Manager.");
    } catch (e) { fail(e); }
  }
  async function saveProvider() { try { setProv(await api.put<Providers>("/api/system/providers", { llm_provider: prov!.llm_provider, llm_model: prov!.llm_model, azure_speech_region: prov!.azure_speech_region })); ok("AI provider updated."); } catch (e) { fail(e); } }
  async function backup() {
    const r = await fetch("/api/system/backup", { method: "POST" });
    if (!r.ok) return fail(new Error("Backup failed"));
    const url = URL.createObjectURL(await r.blob());
    Object.assign(document.createElement("a"), { href: url, download: `english-mastery-backup-${new Date().toISOString().slice(0, 10)}.db` }).click();
    ok("Backup downloaded. To restore, see the user guide.");
  }
  function toggleTheme() { const d = !dark; setDark(d); document.documentElement.classList.toggle("dark", d); localStorage.setItem("ema-theme", d ? "dark" : "light"); }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <h1 className="h1">Settings</h1>
      {msg && <div className="rounded-xl bg-emerald-50 p-3 text-sm text-emerald-800 dark:bg-emerald-500/10 dark:text-emerald-300">{msg}</div>}
      <ErrorBox msg={err} />

      {prov && !prov.keys.gemini && !prov.keys.openai && !prov.keys.anthropic && local && (
        <section className="card space-y-3 !border-gold-500">
          <h2 className="font-semibold">Switch on your AI professor (free, about 2 minutes)</h2>
          <ol className="list-decimal space-y-1 pl-5 text-sm">
            <li>Open <a className="text-brand-500 underline" href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer">aistudio.google.com/apikey</a> and sign in with your Google account.</li>
            <li>Click <b>Create API key</b>, then copy the key (it starts with <code>AIza</code>). No credit card is needed for the free tier.</li>
            <li>Paste it below in <b>AI providers</b> with “Google Gemini (free)” selected, and click <b>Save key</b>.</li>
            <li>Click <b>Run live tests</b>. You're ready when the AI professor shows ✅.</li>
          </ol>
          <p className="text-xs text-ink-400">Free-tier note from Google: content sent on the free tier may be used to improve Google's products. Speech recognition uses Chrome's built-in service, and voices use your device. An OpenAI key is optional; it adds natural AI voices and pause analysis.</p>
        </section>
      )}
      {local && <SelfTest />}
      <section className="card space-y-4">
        <h2 className="font-semibold">AI providers</h2>
        {!local && <p className="muted">For security, API keys and AI providers can only be changed on the computer running the app.</p>}
        {PREVIEW && <p className="rounded-xl bg-ink-50 p-3 text-sm dark:bg-ink-950">Your key is stored only in this browser on this device (never on a server), and is sent only to the provider it belongs to. Use a key with a monthly spending limit. To remove it, delete it here or clear this site's data.</p>}
        {prov && local && (
          <>
            <div className="flex gap-4 text-sm">{Object.entries(prov.keys).map(([k, v]) => <span key={k} className={v ? "text-emerald-500" : "text-ink-400"}>{v ? "●" : "○"} {k} key {v ? "configured" : "not set"}</span>)}</div>
            <div className="grid grid-cols-[160px_1fr_auto] gap-3">
              <select className="input" value={keyInput.provider} onChange={(e) => setKeyInput({ ...keyInput, provider: e.target.value })}><option value="gemini">Google Gemini (free)</option><option value="openai">OpenAI</option><option value="anthropic">Anthropic</option><option value="azure_speech">Azure Speech</option></select>
              <input className="input" type="password" placeholder="Paste API key" value={keyInput.api_key} onChange={(e) => setKeyInput({ ...keyInput, api_key: e.target.value })} />
              <button className="btn-primary" disabled={keyInput.api_key.length < 10} onClick={saveKey}>Save key</button>
            </div>
            <div className="grid grid-cols-[160px_1fr_auto] gap-3">
              <select className="input" value={prov.llm_provider} onChange={(e) => setProv({ ...prov, llm_provider: e.target.value, llm_model: { gemini: "gemini-2.5-flash", openai: "gpt-4o-mini", anthropic: "claude-sonnet-5-5" }[e.target.value as "gemini"] })}><option value="gemini">Google Gemini</option><option value="openai">OpenAI</option><option value="anthropic">Anthropic</option></select>
              <input className="input" value={prov.llm_model} onChange={(e) => setProv({ ...prov, llm_model: e.target.value })} />
              <button className="btn-ghost" onClick={saveProvider}>Use for conversation</button>
            </div>
            <div className="grid grid-cols-[160px_1fr_auto] items-center gap-3">
              <span className="text-sm">Azure region</span>
              <input className="input" placeholder="optional, e.g. canadacentral" value={prov.azure_speech_region} onChange={(e) => setProv({ ...prov, azure_speech_region: e.target.value.trim().toLowerCase() })} />
              <button className="btn-ghost" onClick={saveProvider}>Save region</button>
            </div>
            <p className="text-xs text-ink-400">Voice input (Whisper) and natural voice replies currently use OpenAI, so an OpenAI key is needed for voice even if conversations run on Anthropic. Speech: {prov.stt} · Voice: {prov.tts}. Azure Speech (optional) adds sound-by-sound pronunciation scores.</p>
          </>
        )}
      </section>

      <VoiceSettings accent={p.accent_preference} />

      <section className="card grid grid-cols-2 gap-4">
        <h2 className="col-span-2 font-semibold">Learning preferences</h2>
        <div><label className="label">Name</label><input className="input" value={p.name} onChange={(e) => setP({ ...p, name: e.target.value })} /></div>
        <div><label className="label">Target level</label><select className="input" value={p.target_level} onChange={(e) => setP({ ...p, target_level: e.target.value })}>{["A2", "B1", "B2", "C1", "C2"].map((l) => <option key={l}>{l}</option>)}</select></div>
        <div><label className="label">Daily study time</label><select className="input" value={p.daily_minutes} onChange={(e) => setP({ ...p, daily_minutes: +e.target.value })}>{[30, 60, 90, 120, 180].map((m) => <option key={m} value={m}>{m} min</option>)}</select></div>
        <div><label className="label">Accent</label><select className="input" value={p.accent_preference} onChange={(e) => setP({ ...p, accent_preference: e.target.value as Profile["accent_preference"] })}><option value="en-CA">Canadian</option><option value="en-US">American</option><option value="en-GB">British</option></select></div>
        <div><label className="label">Default corrections</label><select className="input" value={p.correction_mode} onChange={(e) => setP({ ...p, correction_mode: e.target.value })}><option value="immediate">Immediate</option><option value="after_response">After each response</option><option value="end_of_conversation">End of conversation</option><option value="strict">Strict examination</option></select></div>
        <div><label className="label">Daily reminder</label><input type="time" className="input" value={p.reminder_time ?? ""} onChange={(e) => setP({ ...p, reminder_time: e.target.value || null })} />
          <p className="mt-1 text-xs text-ink-400">Shows a Windows notification while the app is open. To open the app automatically at this time, run install-reminder.bat.</p></div>
        <label className="flex items-center gap-2 self-end pb-2 text-sm"><input type="checkbox" checked={p.french_explanations} onChange={(e) => setP({ ...p, french_explanations: e.target.checked })} /> French explanations</label>
        <div className="col-span-2 flex justify-end"><button className="btn-primary" onClick={saveProfile}>Save preferences</button></div>
      </section>

      <section className="card flex items-center justify-between">
        <div><h2 className="font-semibold">Appearance & data</h2><p className="muted">{PREVIEW ? "Your progress is saved in this browser on this device." : "Your data lives in %APPDATA%\\EnglishMasteryAI on this computer."}</p></div>
        <div className="flex gap-2"><button className="btn-ghost" onClick={toggleTheme}>{dark ? "Light mode" : "Dark mode"}</button>{local && <button className="btn-ghost" onClick={backup}>Back up progress</button>}</div>
      </section>

      <section className="card">
        <h2 className="mb-3 font-semibold">What works in this version</h2>
        <table className="w-full text-sm"><tbody>{features.map((f) => (
          <tr key={f.id} className="border-t border-ink-100 dark:border-ink-800"><td className="py-2">{f.name}</td>
            <td className="py-2 text-ink-400">{f.status === "planned" ? `Planned · Phase ${f.phase}` : f.needs?.length ? `Needs ${f.needs.map((n) => NEEDS[n]).join(", ")}` : "Works offline"}</td>
            <td className={`py-2 text-right ${f.status === "available" ? "text-emerald-500" : "text-gold-500"}`}>{f.status}</td></tr>
        ))}</tbody></table>
      </section>
    </div>
  );
}

function VoiceSettings({ accent }: { accent: string }) {
  const [prefs, setPrefs] = useState<VoicePrefs>(getVoicePrefs());
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>(englishVoices());
  useEffect(() => {
    const update = () => setVoices(englishVoices());
    update();
    if ("speechSynthesis" in window) speechSynthesis.onvoiceschanged = update;
  }, []);
  const save = (p: VoicePrefs) => { setPrefs(p); setVoicePrefs(p); };
  const label: Record<string, string> = { "en-us": "American", "en-gb": "British", "en-ca": "Canadian", "en-au": "Australian", "en-ie": "Irish", "en-in": "Indian" };
  const lang = (v: SpeechSynthesisVoice) => v.lang.replace("_", "-").toLowerCase();
  return (
    <section className="card space-y-4">
      <div><h2 className="font-semibold">Voices</h2><p className="muted">Voices installed on this device: free, and they work offline. Your accent setting (below) chooses American, British or Canadian English. With an OpenAI key, conversation replies use natural AI voices.</p></div>
      <div className="grid grid-cols-3 gap-4">
        <div><label className="label">Voice gender</label>
          <select className="input" value={prefs.gender} onChange={(e) => save({ ...prefs, gender: e.target.value as VoicePrefs["gender"], voiceName: null })}>
            <option value="any">Any</option><option value="female">Female</option><option value="male">Male</option></select></div>
        <div><label className="label">Specific voice</label>
          <select className="input" value={prefs.voiceName ?? ""} onChange={(e) => save({ ...prefs, voiceName: e.target.value || null })}>
            <option value="">Automatic for my accent</option>
            {voices.map((v) => <option key={v.name} value={v.name}>{label[lang(v)] ?? v.lang} · {v.name}{voiceGender(v) !== "unknown" ? ` (${voiceGender(v)})` : ""}</option>)}
          </select></div>
        <div><label className="label">Speaking speed: {prefs.rate.toFixed(2)}×</label>
          <input type="range" min={0.6} max={1.4} step={0.05} value={prefs.rate} className="w-full" onChange={(e) => save({ ...prefs, rate: +e.target.value })} /></div>
      </div>
      <button className="btn-ghost" onClick={() => speakLocal("Hello! This is how I will sound when we practise together.", accent)}>🔊 Test this voice</button>
      {voices.length === 0 && <p className="text-xs text-gold-500">No English voices were reported by this browser yet. In Chrome they appear after a moment; on Windows you can add more under Settings › Time & language › Speech.</p>}
    </section>
  );
}
