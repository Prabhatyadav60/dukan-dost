import { useEffect, useRef } from 'react';
import { api } from '../api/client';
import { ErrorBox, Loading } from '../components/States';
import { timeIST } from '../lib/dates';
import { useFetch } from '../lib/useFetch';
import { s } from '../strings';

export default function Assistant() {
  const { data, error, loading, reload } = useFetch(() => api.thread(50), [], 4000);
  const end = useRef<HTMLDivElement>(null);
  const count = data?.messages.length ?? 0;

  useEffect(() => {
    end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [count]);

  return (
    <main className="chat">
      <h1 className="h" style={{ fontSize: 20 }}>{s.assistant.title}</h1>
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
            {m.kind === 'voice' ? `“${m.text}”` : m.text}
            <span className="t">{timeIST(m.created_at)}</span>
          </div>
        );
      })}
      <div ref={end} />
    </main>
  );
}
