/**
 * Hands-free voice activity detection (VAD) for natural conversation.
 *
 * - Calibrates to the room's noise floor for ~1 s.
 * - Detects speech onset (energy above threshold for >= 250 ms) -> onSpeechStart
 *   (used for barge-in: the AI voice stops as soon as you talk).
 * - After speech, 1.2 s of silence ends the utterance -> onUtterance(blob).
 * Uses the browser's echo cancellation so the AI's own voice is not picked up.
 */
export interface HandsFreeOptions {
  onUtterance: (audio: Blob) => void;
  onSpeechStart?: () => void;
  onLevel?: (level: number, speaking: boolean) => void;
  silenceMs?: number;
  minSpeechMs?: number;
}

export class HandsFree {
  private stream: MediaStream | null = null;
  private ctx: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private rec: MediaRecorder | null = null;
  private chunks: Blob[] = [];
  private raf = 0;
  private threshold = 0.02;
  private calib: number[] = [];
  private aboveSince = 0;
  private lastVoice = 0;
  private speaking = false;
  private hadSpeech = false;
  private segmentStart = 0;
  paused = false;

  constructor(private o: HandsFreeOptions) {}

  async start() {
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
    this.ctx = new AudioContext();
    const src = this.ctx.createMediaStreamSource(this.stream);
    this.analyser = this.ctx.createAnalyser();
    this.analyser.fftSize = 1024;
    src.connect(this.analyser);
    this.newSegment();
    const buf = new Float32Array(this.analyser.fftSize);
    const t0 = performance.now();

    const tick = () => {
      this.analyser!.getFloatTimeDomainData(buf);
      let sum = 0;
      for (const v of buf) sum += v * v;
      const rms = Math.sqrt(sum / buf.length);
      const now = performance.now();

      if (now - t0 < 1000) {
        this.calib.push(rms);
      } else if (this.calib.length) {
        const floor = this.calib.sort((a, b) => a - b)[Math.floor(this.calib.length * 0.8)] || 0.005;
        this.threshold = Math.max(0.015, floor * 3);
        this.calib = [];
      } else if (!this.paused) {
        const above = rms > this.threshold;
        if (above) {
          this.lastVoice = now;
          if (!this.aboveSince) this.aboveSince = now;
          if (!this.speaking && now - this.aboveSince >= (this.o.minSpeechMs ?? 250)) {
            this.speaking = true;
            this.hadSpeech = true;
            this.o.onSpeechStart?.();
          }
        } else {
          this.aboveSince = 0;
          if (this.speaking && now - this.lastVoice > (this.o.silenceMs ?? 1200)) {
            this.speaking = false;
            this.finishSegment();
          }
        }
        // Drop long silent segments so uploads stay small
        if (!this.hadSpeech && now - this.segmentStart > 15000) this.restartSegment();
      }
      this.o.onLevel?.(Math.min(1, rms / (this.threshold * 4)), this.speaking);
      this.raf = requestAnimationFrame(tick);
    };
    this.raf = requestAnimationFrame(tick);
  }

  private newSegment() {
    const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "";
    this.rec = new MediaRecorder(this.stream!, mime ? { mimeType: mime } : undefined);
    this.chunks = [];
    this.hadSpeech = false;
    this.segmentStart = performance.now();
    this.rec.ondataavailable = (e) => e.data.size && this.chunks.push(e.data);
    this.rec.start(250);
  }

  private restartSegment() {
    if (!this.rec) return;
    this.rec.onstop = () => this.newSegment();
    this.rec.stop();
  }

  private finishSegment() {
    if (!this.rec) return;
    const rec = this.rec;
    rec.onstop = () => {
      const blob = new Blob(this.chunks, { type: "audio/webm" });
      if (this.stream) this.newSegment();
      if (blob.size > 2000) this.o.onUtterance(blob);
    };
    rec.stop();
  }

  stop() {
    cancelAnimationFrame(this.raf);
    if (this.rec && this.rec.state !== "inactive") { this.rec.onstop = null; this.rec.stop(); }
    this.stream?.getTracks().forEach((t) => t.stop());
    this.ctx?.close();
    this.stream = null;
    this.rec = null;
  }
}
