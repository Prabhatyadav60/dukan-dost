import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { api, ApiError } from '../api/client';
import { ErrorBox, Loading } from '../components/States';
import { shortDate } from '../lib/dates';
import { formatPaise } from '../lib/money';
import { useFetch } from '../lib/useFetch';
import { s } from '../strings';

/** Public customer pay page (mock Paytm link). No app chrome. */
export default function Pay() {
  const { linkId = '' } = useParams();
  const { data, error, loading, reload } = useFetch(() => api.publicPay(linkId), [linkId]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function pay() {
    setBusy(true);
    setMsg(null);
    try {
      await api.publicPayNow(linkId);
      reload();
    } catch (e) {
      if (e instanceof ApiError && (e.code === 'link_already_paid' || e.code === 'link_expired')) reload();
      else setMsg(e instanceof ApiError ? e.message : s.common.genericError);
    } finally {
      setBusy(false);
    }
  }

  if (loading && !data) return <main className="screen plain"><Loading /></main>;
  if (error && !data) {
    return <main className="screen plain">{error.status === 404 ? <p className="empty">{s.pay.notFound}</p> : <ErrorBox error={error} onRetry={reload} />}</main>;
  }
  if (!data) return null;

  return (
    <>
      <header className="payhead">
        <p className="sub">{s.pay.from}</p>
        <h1 className="h">{data.shop_name}</h1>
      </header>
      <main className="screen plain" style={{ paddingTop: 18 }}>
        <p className="sub">{s.pay.owed(data.customer_name)}</p>
        <p className="big" style={{ fontSize: 42 }}>{formatPaise(data.amount_paise)}</p>
        {data.items.length > 0 && (
          <div className="card">
            {data.items.map((it, i) => (
              <div className="row" key={i}>
                <span>{shortDate(it.date)}{it.items.length ? ` · ${it.items.join(', ')}` : ''}</span>
                <span>{formatPaise(it.amount_paise)}</span>
              </div>
            ))}
          </div>
        )}
        {data.status === 'created' && <p className="sub">{s.pay.note}</p>}
        {msg && <p className="err" role="alert">{msg}</p>}
        <div style={{ marginTop: 'auto' }} className="stack">
          {data.status === 'created' && (
            <button className="btn pay" disabled={busy} onClick={pay}>{busy ? s.pay.paying : s.pay.pay(formatPaise(data.amount_paise))}</button>
          )}
          {data.status === 'paid' && <p className="ok" style={{ textAlign: 'center', fontSize: 18 }}>✓ {s.pay.paid}</p>}
          {data.status === 'expired' && <p className="warn-text" style={{ textAlign: 'center' }}>{s.pay.expired}</p>}
          <p className="sub" style={{ textAlign: 'center' }}>{s.pay.demo}</p>
        </div>
      </main>
    </>
  );
}
