import { api, ApiError } from "./api";
import { playableUrl } from "./preview";
import { BrowserTranscriber } from "./browserStt";

// ------------------------------------------------------------------ voice preferences (this browser)
export interface VoicePrefs { voiceName: string | null; gender: "female" | "male" | "any"; rate: number }
const PREF_KEY = "ema-voice";

export function getVoicePrefs(): VoicePrefs {
  try { return { voiceName: null, gender: "any", rate: 1, ...JSON.parse(localStorage.getItem(PREF_KEY) ?? "{}") }; }
  catch { return { voiceName: null, gender: "any", rate: 1 }; }
}
export function setVoicePrefs(p: VoicePrefs) { try { localStorage.setItem(PREF_KEY, JSON.stringify(p)); } catch { /* storage unavailable */ } }

const FEMALE = /female|woman|aria|jenny|zira|hazel|susan|libby|sonia|clara|linda|samantha|karen|moira|tessa|victoria|allison|ava|serena|natasha|emma|olivia|catherine|heather|google uk english female|google us english/i;
const MALE = /\bmale\b|\bman\b|guy|davis|david|mark|george|ryan|richard|liam|alex|daniel|fred|tom|oliver|james|william|brian|christopher|eric|google uk english male/i;

export function voiceGender(v: SpeechSynthesisVoice): "female" | "male" | "unknown" {
  if (/female/i.test(v.name)) return "female";
  if (MALE.test(v.name)) return "male";
  if (FEMALE.test(v.name)) return "female";
  return "unknown";
}

export const englishVoices = () =>
  ("speechSynthesis" in window ? speechSynthesis.getVoices() : []).filter((v) => v.lang.replace("_", "-").toLowerCase().startsWith("en"));

/** Best installed voice for an accent, honouring the learner's chosen voice and gender. */
export function pickVoice(accent: string): SpeechSynthesisVoice | undefined {
  const prefs = getVoicePrefs();
  const all = englishVoices();
  const norm = (l: string) => l.replace("_", "-").toLowerCase();
  const chosen = prefs.voiceName ? all.find((v) => v.name === prefs.voiceName) : undefined;
  if (chosen && norm(chosen.lang) === accent.toLowerCase()) return chosen;
  const sameAccent = all.filter((v) => norm(v.lang) === accent.toLowerCase());
  const byGender = prefs.gender === "any" ? sameAccent : sameAccent.filter((v) => voiceGender(v) === prefs.gender);
  return byGender[0] ?? sameAccent[0] ?? chosen ?? all[0];
}

/** Free voice using the voices installed on this device (works offline). */
export function speakLocal(text: string, accent = "en-CA", rate?: number, onEnd?: () => void) {
  if (!("speechSynthesis" in window)) { onEnd?.(); return; }
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = accent;
  u.rate = rate ?? getVoicePrefs().rate;
  const v = pickVoice(accent);
  if (v) u.voice = v;
  u.onend = () => onEnd?.();
  u.onerror = () => onEnd?.();
  window.speechSynthesis.speak(u);
}

let current: HTMLAudioElement | null = null;
let aiVoice: boolean | null = null; // null = unknown, false = no OpenAI key configured

export function stopAudio() {
  current?.pause();
  current = null;
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
}

/** Natural AI voice (OpenAI, if configured); otherwise the device voice. onEnd fires when speech finishes. */
export async function speakAI(text: string, accent: string, onEnd?: () => void): Promise<"ai" | "local"> {
  stopAudio();
  if (aiVoice !== false) {
    try {
      const r = await api.post<{ mime: string; audio_base64: string }>("/api/conversation/tts", { text });
      aiVoice = true;
      const a = new Audio(`data:${r.mime};base64,${r.audio_base64}`);
      current = a;
      a.playbackRate = getVoicePrefs().rate;
      a.onended = () => onEnd?.();
      await a.play();
      return "ai";
    } catch (e) {
      if ((e as ApiError).status === 412) aiVoice = false;
    }
  }
  speakLocal(text, accent, undefined, onEnd);
  return "local";
}
export const resetVoiceDetection = () => { aiVoice = null; };

/**
 * Microphone recorder (MediaRecorder, webm/opus). When Chrome's speech recognition is available it
 * also transcribes at the same time, so speaking features work without any paid speech service.
 */
export class Recorder {
  private rec: MediaRecorder | null = null;
  private chunks: Blob[] = [];
  private stream: MediaStream | null = null;
  private stt = new BrowserTranscriber();
  private sttOn = false;
  transcript = "";
  duration = 0;

  async start(lang = "en-US") {
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
    const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "";
    this.rec = new MediaRecorder(this.stream, mime ? { mimeType: mime } : undefined);
    this.chunks = [];
    this.transcript = "";
    this.duration = 0;
    this.rec.ondataavailable = (e) => e.data.size && this.chunks.push(e.data);
    this.rec.start();
    this.sttOn = this.stt.start(lang);
  }

  stop(): Promise<Blob> {
    return new Promise((resolve) => {
      if (!this.rec) return resolve(new Blob());
      this.rec.onstop = async () => {
        this.stream?.getTracks().forEach((t) => t.stop());
        if (this.sttOn) { const r = await this.stt.stop(); this.transcript = r.text; this.duration = r.duration; }
        resolve(new Blob(this.chunks, { type: "audio/webm" }));
      };
      this.rec.stop();
    });
  }

  /** Adds the browser transcript to an upload, so the engine can use it when Whisper isn't configured. */
  attach(fd: FormData, transcriptField = "transcript", durationField = "duration") {
    if (this.transcript) { fd.append(transcriptField, this.transcript); fd.append(durationField, String(this.duration)); }
  }
}

/** URL of natural-voice audio for a script line (generated once by the engine, then cached). */
export function audioUrl(text: string, voice: string) {
  return `/api/listening/line?voice=${encodeURIComponent(voice)}&text=${encodeURIComponent(text)}`;
}

/** Play one line in a natural voice, falling back to the device voice for the accent. */
export function playLine(text: string, voice: string, accent: string, rate = 1): Promise<void> {
  stopAudio();
  return new Promise((resolve) => {
    const fallback = () => speakLocal(text, accent, rate, resolve);
    if (aiVoice === false) return fallback();
    const a = new Audio();
    current = a;
    a.onended = () => resolve();
    a.onerror = fallback;
    playableUrl(audioUrl(text, voice)).then((src) => { a.src = src; a.playbackRate = rate; return a.play(); }).catch(fallback);
  });
}
