/**
 * Chrome's built-in speech recognition (Web Speech API). Free and needs no key;
 * audio is processed by the browser vendor's speech service. Gives text only (no word timings).
 */
type Rec = {
  lang: string; continuous: boolean; interimResults: boolean;
  onresult: ((e: any) => void) | null; onerror: ((e: any) => void) | null; onend: (() => void) | null; onspeechstart: (() => void) | null; // eslint-disable-line @typescript-eslint/no-explicit-any
  start(): void; stop(): void; abort(): void;
};

function ctor(): (new () => Rec) | null {
  const w = window as unknown as { SpeechRecognition?: new () => Rec; webkitSpeechRecognition?: new () => Rec };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export const browserSttAvailable = () => ctor() !== null;

/** One-shot capture: collects everything said between start() and stop(). */
export class BrowserTranscriber {
  private rec: Rec | null = null;
  private finals: string[] = [];
  private interim = "";
  private startedAt = 0;
  private running = false;
  private ended: Promise<void> = Promise.resolve();

  start(lang: string) {
    const C = ctor();
    if (!C) return false;
    this.finals = []; this.interim = ""; this.startedAt = performance.now(); this.running = true;
    const rec = new C();
    rec.lang = lang; rec.continuous = true; rec.interimResults = true;
    rec.onresult = (e) => {
      this.interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        if (r.isFinal) this.finals.push(r[0].transcript.trim()); else this.interim += r[0].transcript;
      }
    };
    this.ended = new Promise((resolve) => {
      rec.onend = () => { if (this.running) { try { rec.start(); return; } catch { /* fallthrough */ } } resolve(); };
    });
    rec.onerror = () => { /* 'no-speech' etc.: onend follows */ };
    try { rec.start(); this.rec = rec; return true; } catch { return false; }
  }

  async stop(): Promise<{ text: string; duration: number }> {
    const duration = (performance.now() - this.startedAt) / 1000;
    if (!this.rec) return { text: "", duration };
    this.running = false;
    this.rec.stop();
    await Promise.race([this.ended, new Promise((r) => setTimeout(r, 1500))]);
    const text = [...this.finals, this.interim.trim()].filter(Boolean).join(" ").trim();
    this.rec = null;
    return { text, duration };
  }
}

/** Hands-free listening: emits each finished sentence; restarts itself until stopped. */
export class BrowserListener {
  private rec: Rec | null = null;
  private active = false;
  paused = false;
  private segStart = 0;

  constructor(private o: { lang: string; onSentence: (text: string, durationSec: number) => void; onSpeechStart?: () => void; onInterim?: (t: string) => void }) {}

  start() {
    const C = ctor();
    if (!C) return false;
    this.active = true;
    const rec = new C();
    rec.lang = this.o.lang; rec.continuous = true; rec.interimResults = true;
    rec.onspeechstart = () => { this.segStart = performance.now(); this.o.onSpeechStart?.(); };
    rec.onresult = (e) => {
      if (this.paused) return;
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        if (r.isFinal) {
          const text = r[0].transcript.trim();
          const dur = this.segStart ? (performance.now() - this.segStart) / 1000 : text.split(/\s+/).length / 2.5;
          this.segStart = performance.now();
          if (text) this.o.onSentence(text, dur);
        } else interim += r[0].transcript;
      }
      this.o.onInterim?.(interim);
    };
    rec.onend = () => { if (this.active) { try { rec.start(); } catch { /* already started */ } } };
    rec.onerror = () => {};
    try { rec.start(); this.rec = rec; return true; } catch { return false; }
  }

  stop() { this.active = false; this.rec?.abort(); this.rec = null; }
}
