import { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import { useAssistant } from '../assistant';
import { CameraIcon } from '../components/Icons';
import { MicButton } from '../components/MicButton';
import { ErrorBox, Loading } from '../components/States';
import { useToast } from '../components/Toast';
import { timeIST } from '../lib/dates';
import { useFetch } from '../lib/useFetch';
import { s } from '../strings';

/** The single conversation: entries, questions, bills and shelf photos all land here. */
export default function Assistant() {
  const a = useAssistant();
  const toast = useToast();
  const { data, error, loading, reload } = useFetch(() => api.thread(80), [a.threadTick], 4000);
  const [text, setText] = useState('');
  const end = useRef<HTMLDivElement>(null);
  const count = data?.messages.length ?? 0;

  useEffect(() => {
    end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [count, a.busy]);

  async function send() {
    const t = text.trim();
    if (!t || a.busy) return;
    setText('');
    if (!(await a.submitText(t))) setText(t);
  }

  return (
    <>
      <main className="chat with-composer">
        <div>
          <h1 className="h" style={{ fontSize: 20 }}>{s.assistant.title}</h1>
          <p className="sub">{s.assistant.sub}</p>
        </div>
        {loading && !data && <Loading />}
        {error && !data && <ErrorBox error={error} onRetry={reload} />}
        {data && data.messages.length === 0 && <p className="sub">{s.assistant.empty}</p>}
        {data?.messages.map((m) => {
          const me = m.role === 'merchant';
          const cls = 'bub' + (me ? ' me' : '') + (m.kind === 'alert' ? ' hl' : '');
          return (
            <div key={m.id} className={cls}>
              {m.kind === 'voice' && <b>{s.assistant.voiceNote}</b>}
              {m.kind === 'photo' && <b>{s.assistant.photo}</b>}
              <span style={{ whiteSpace: 'pre-line' }}>{m.kind === 'voice' ? `“${m.text}”` : m.text}</span>
              <span className="t">{timeIST(m.created_at)}</span>
            </div>
          );
        })}
        {a.busy && <div className="bub typing" role="status">{s.assistant.thinking}</div>}
        <div ref={end} className="chat-end" />
      </main>

      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
      >
        <button type="button" className="iconbtn" aria-label={s.assistant.camera} onClick={a.pickPhoto} disabled={a.busy}>
          <CameraIcon />
        </button>
        <input
          value={text}
          maxLength={300}
          placeholder={s.assistant.placeholder}
          aria-label={s.assistant.placeholder}
          onChange={(e) => setText(e.target.value)}
        />
        {text.trim() ? (
          <button className="btn small" aria-label="Chat mein bhejein" disabled={a.busy}>{s.voice.send}</button>
        ) : (
          <MicButton compact onAudio={(b, n) => void a.submitAudio(b, n)} onError={toast} />
        )}
      </form>
    </>
  );
}
