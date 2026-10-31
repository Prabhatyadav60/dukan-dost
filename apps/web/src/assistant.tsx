import { createContext, useCallback, useContext, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { api, ApiError, ttsAudio } from './api/client';
import type { BillScanResponse, VoiceParseResponse } from './api/types';
import { BillReviewSheet } from './components/BillReviewSheet';
import { ConfirmSheet } from './components/ConfirmSheet';
import { useToast } from './components/Toast';
import { resizeImage } from './lib/resizeImage';
import { s } from './strings';

type Sheet =
  | { k: 'none' }
  | { k: 'typing' }
  | { k: 'confirm'; parsed: VoiceParseResponse | null; source: 'voice' | 'text' | 'manual' }
  | { k: 'photoKind'; files: File[] }
  | { k: 'bill'; scan: BillScanResponse | null; error: string | null };

interface AssistantApi {
  /** A request is in flight (shows the "Soch raha hoon…" bubble). */
  busy: boolean;
  /** Bumped whenever the thread has new content worth refetching. */
  threadTick: number;
  submitText: (text: string) => Promise<boolean>;
  submitAudio: (blob: Blob, filename: string) => Promise<void>;
  openTyping: () => void;
  pickPhoto: () => void;
  /** Read-aloud: the text currently playing / loading, keyed by the message text. */
  speaking: string | null;
  speakLoading: string | null;
  toggleSpeak: (text: string) => void;
  /** Auto-play the answer when the merchant asked by voice. */
  autoRead: boolean;
  setAutoRead: (v: boolean) => void;
}

const AUTO_READ_KEY = 'dd_auto_read';

function readAutoPref(): boolean {
  try {
    return localStorage.getItem(AUTO_READ_KEY) !== 'off';
  } catch {
    return true;
  }
}

const Ctx = createContext<AssistantApi | null>(null);

export function useAssistant(): AssistantApi {
  const v = useContext(Ctx);
  if (!v) throw new Error('useAssistant outside AssistantProvider');
  return v;
}

/**
 * One conversation for everything: voice/text entries, shop questions, bill and shelf photos.
 * Used by both the tab-bar mic and the chat composer; every action lands in /assistant.
 */
export function AssistantProvider({ children }: { children: React.ReactNode }) {
  const [sheet, setSheet] = useState<Sheet>({ k: 'none' });
  const [busy, setBusy] = useState(false);
  const [threadTick, setTick] = useState(0);
  const [typed, setTyped] = useState('');
  const fileInput = useRef<HTMLInputElement>(null);
  const toast = useToast();
  const nav = useNavigate();
  const loc = useLocation();

  const bump = useCallback(() => setTick((t) => t + 1), []);

  // --- read aloud (one player for the whole app; replaying a message reuses its audio)
  const player = useRef<HTMLAudioElement | null>(null);
  const audioUrls = useRef(new Map<string, string>());
  const [speaking, setSpeaking] = useState<string | null>(null);
  const [speakLoading, setSpeakLoading] = useState<string | null>(null);
  const [autoRead, setAutoReadState] = useState(readAutoPref);

  const stopSpeaking = useCallback(() => {
    player.current?.pause();
    setSpeaking(null);
  }, []);

  const speak = useCallback(async (text: string) => {
    stopSpeaking();
    setSpeakLoading(text);
    try {
      let url = audioUrls.current.get(text);
      if (!url) {
        url = URL.createObjectURL(await ttsAudio(text));
        audioUrls.current.set(text, url);
      }
      const audio = player.current ?? (player.current = new Audio());
      audio.src = url;
      audio.onended = () => setSpeaking(null);
      setSpeaking(text);
      await audio.play();
    } catch {
      setSpeaking(null);
      toast(s.assistant.ttsFailed);
    } finally {
      setSpeakLoading((t) => (t === text ? null : t));
    }
  }, [stopSpeaking, toast]);
  const goChat = useCallback(() => {
    if (loc.pathname !== '/assistant') nav('/assistant');
  }, [loc.pathname, nav]);

  async function parse(p: Promise<VoiceParseResponse>, source: 'voice' | 'text'): Promise<boolean> {
    setSheet({ k: 'none' });
    goChat();
    setBusy(true);
    bump(); // the server records the merchant's message first
    try {
      const r = await p;
      bump();
      if (r.kind === 'answer' || !r.draft) {
        // asked by voice → answer by voice
        if (source === 'voice' && autoRead && r.answer) void speak(r.answer);
        return true;
      }
      setSheet({ k: 'confirm', parsed: r, source });
      return true;
    } catch (e) {
      if (e instanceof ApiError && e.code === 'ai_unavailable') {
        setSheet({ k: 'confirm', parsed: null, source: 'manual' });
        return true;
      }
      toast(e instanceof ApiError && e.code !== 'network' ? (e.message || s.voice.sttFailed) : s.common.networkError);
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function onPhotoKind(kind: 'bill' | 'shelf', files: File[]) {
    setSheet({ k: 'none' });
    goChat();
    setBusy(true);
    try {
      if (kind === 'bill') {
        const blobs = await Promise.all(files.slice(0, 3).map((f) => resizeImage(f)));
        try {
          const r = await api.scanBill(blobs);
          setSheet({ k: 'bill', scan: r, error: null });
        } catch (e) {
          setSheet({ k: 'bill', scan: null, error: e instanceof ApiError && e.code === 'network' ? s.common.networkError : s.scan.failed });
        }
      } else {
        await api.shelfScan(await resizeImage(files[0]));
        toast(s.assistant.shelfDone);
      }
    } catch (e) {
      toast(e instanceof ApiError ? e.message : s.shelf.failed);
    } finally {
      setBusy(false);
      bump();
    }
  }

  function saved(message: string) {
    setTyped('');
    setSheet({ k: 'none' });
    toast(message);
    bump();
    goChat();
  }

  const value: AssistantApi = {
    busy,
    threadTick,
    submitText: (text) => parse(api.voiceParseText(text), 'text'),
    submitAudio: async (blob, filename) => {
      await parse(api.voiceParseAudio(blob, filename), 'voice');
    },
    openTyping: () => setSheet({ k: 'typing' }),
    pickPhoto: () => fileInput.current?.click(),
    speaking,
    speakLoading,
    toggleSpeak: (text) => (speaking === text ? stopSpeaking() : void speak(text)),
    autoRead,
    setAutoRead: (v) => {
      setAutoReadState(v);
      try {
        localStorage.setItem(AUTO_READ_KEY, v ? 'on' : 'off');
      } catch {
        /* preference just won't persist */
      }
    },
  };

  return (
    <Ctx.Provider value={value}>
      {children}
      <input
        ref={fileInput}
        type="file"
        accept="image/*"
        capture="environment"
        multiple
        hidden
        data-testid="chat-photo-input"
        onChange={(e) => {
          const files = Array.from(e.target.files ?? []);
          e.target.value = '';
          if (files.length) setSheet({ k: 'photoKind', files });
        }}
      />

      {sheet.k === 'typing' && (
        <div className="dim" onClick={() => setSheet({ k: 'none' })}>
          <form
            className="sheet"
            onClick={(e) => e.stopPropagation()}
            onSubmit={(e) => {
              e.preventDefault();
              const t = typed.trim();
              if (t) void parse(api.voiceParseText(t), 'text').then((ok) => ok && setTyped(''));
            }}
          >
            <div className="grab" />
            <div className="textrow">
              <input autoFocus maxLength={300} value={typed} placeholder={s.voice.typePlaceholder} onChange={(e) => setTyped(e.target.value)} />
              <button className="btn small" disabled={!typed.trim()}>{s.voice.send}</button>
            </div>
          </form>
        </div>
      )}

      {sheet.k === 'photoKind' && (
        <div className="dim" onClick={() => setSheet({ k: 'none' })}>
          <div className="sheet" role="dialog" aria-modal="true" aria-label={s.assistant.photoWhat} onClick={(e) => e.stopPropagation()}>
            <div className="grab" />
            <p className="h" style={{ fontSize: 19 }}>{s.assistant.photoWhat}</p>
            <div className="btns">
              <button className="btn" onClick={() => void onPhotoKind('bill', sheet.files)}>{s.assistant.photoBill}</button>
              <button className="btn ghost" onClick={() => void onPhotoKind('shelf', sheet.files)}>{s.assistant.photoShelf}</button>
            </div>
          </div>
        </div>
      )}

      {sheet.k === 'confirm' && (
        <ConfirmSheet parsed={sheet.parsed} source={sheet.source} onClose={() => setSheet({ k: 'none' })} onSaved={saved} />
      )}

      {sheet.k === 'bill' && (
        <BillReviewSheet asSheet scan={sheet.scan} error={sheet.error} onClose={() => setSheet({ k: 'none' })} onSaved={saved} />
      )}
    </Ctx.Provider>
  );
}
