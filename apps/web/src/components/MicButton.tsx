import { useEffect, useRef, useState } from 'react';
import { extensionFor, MAX_RECORD_MS, pickMimeType } from '../lib/recorder';
import { s } from '../strings';
import { MicIcon } from './Icons';

interface Props {
  onAudio: (blob: Blob, filename: string) => void;
  onError: (msg: string) => void;
  /** Small inline variant for the chat composer. */
  compact?: boolean;
}

const BARS = 18;

/** Press and hold to record; release to send. Auto-stops at 30 s. */
export function MicButton({ onAudio, onError, compact }: Props) {
  const [recording, setRecording] = useState(false);
  const [levels, setLevels] = useState<number[]>(() => Array(BARS).fill(4));
  const rec = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const stopTimer = useRef<number>();
  const raf = useRef<number>();
  const audioCtx = useRef<AudioContext | null>(null);
  const wantStop = useRef(false);

  useEffect(() => () => cleanup(), []);

  function cleanup() {
    window.clearTimeout(stopTimer.current);
    if (raf.current) cancelAnimationFrame(raf.current);
    audioCtx.current?.close().catch(() => {});
    audioCtx.current = null;
  }

  async function start() {
    wantStop.current = false;
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      onError(s.voice.micBlocked);
      return;
    }
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      onError(s.voice.micBlocked);
      return;
    }
    const mime = pickMimeType();
    const r = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
    chunks.current = [];
    r.ondataavailable = (e) => e.data.size && chunks.current.push(e.data);
    r.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      cleanup();
      setRecording(false);
      const type = r.mimeType || mime || 'audio/webm';
      const blob = new Blob(chunks.current, { type });
      if (blob.size > 0) onAudio(blob, `voice.${extensionFor(type)}`);
    };
    rec.current = r;
    r.start();
    setRecording(true);
    stopTimer.current = window.setTimeout(stop, MAX_RECORD_MS);

    try {
      const ctx = new AudioContext();
      audioCtx.current = ctx;
      const an = ctx.createAnalyser();
      an.fftSize = 64;
      ctx.createMediaStreamSource(stream).connect(an);
      const buf = new Uint8Array(an.frequencyBinCount);
      const tick = () => {
        an.getByteFrequencyData(buf);
        setLevels(Array.from({ length: BARS }, (_, i) => 4 + (buf[i % buf.length] / 255) * 26));
        raf.current = requestAnimationFrame(tick);
      };
      tick();
    } catch {
      /* waveform is decorative */
    }
    // Released before getUserMedia resolved.
    if (wantStop.current) stop();
  }

  function stop() {
    wantStop.current = true;
    if (rec.current && rec.current.state === 'recording') rec.current.stop();
  }

  return (
    <>
      <button
        type="button"
        className={'mic' + (compact ? ' compact' : '') + (recording ? ' rec' : '')}
        aria-label={compact ? 'Chat mein bolein (dabaakar rakhein)' : 'Bolne ke liye dabaakar rakhein'}
        onPointerDown={(e) => {
          e.preventDefault();
          (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
          void start();
        }}
        onPointerUp={stop}
        onPointerCancel={stop}
        onContextMenu={(e) => e.preventDefault()}
        onKeyDown={(e) => {
          if ((e.key === ' ' || e.key === 'Enter') && !recording && !e.repeat) void start();
        }}
        onKeyUp={(e) => {
          if (e.key === ' ' || e.key === 'Enter') stop();
        }}
      >
        <MicIcon />
      </button>
      {recording && (
        <div className="dim" style={{ pointerEvents: 'none' }}>
          <div className="sheet" style={{ alignItems: 'center', paddingBottom: 110 }}>
            <div className="wave" aria-hidden="true">
              {levels.map((h, i) => <i key={i} style={{ height: h }} />)}
            </div>
            <p className="sub">{s.voice.listening}</p>
          </div>
        </div>
      )}
    </>
  );
}
