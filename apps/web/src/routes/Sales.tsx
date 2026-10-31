import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import type { SalesToday } from '../api/types';
import { CashReceivedSheet } from '../components/CashReceivedSheet';
import { Empty, ErrorBox, Loading } from '../components/States';
import { useToast } from '../components/Toast';
import { timeIST } from '../lib/dates';
import { formatPaise } from '../lib/money';
import { useFetch } from '../lib/useFetch';
import { s } from '../strings';

type View = 'people' | 'all';

/** Every rupee of today's sales: who paid, how, and when. */
function allPayments(d: SalesToday) {
  const rows = [
    ...d.qr.map((q) => ({ id: q.id, ts: q.ts, amount: q.amount_paise, who: q.payer_name ?? q.payer_vpa ?? s.sales.upiCustomer, sub: q.payer_name ? q.payer_vpa : null, channel: 'qr' as const })),
    ...d.cash.map((c) => ({ id: c.id, ts: c.ts, amount: c.amount_paise, who: c.note || s.sales.cashSale, sub: null, channel: 'cash' as const })),
  ];
  return rows.sort((a, b) => b.ts.localeCompare(a.ts));
}

export default function Sales() {
  const { data, error, loading, reload } = useFetch(api.salesToday, [], 15_000);
  const [view, setView] = useState<View>('people');
  const [cashOpen, setCashOpen] = useState(false);
  const toast = useToast();

  return (
    <main className="screen">
      <Link to="/" className="sub" style={{ minHeight: 24 }}>{s.sales.back}</Link>
      <div>
        <p className="sub">{s.sales.title}</p>
        {data && <h1 className="big">{formatPaise(data.total_paise)}</h1>}
        {data && <p className="sub">{s.sales.split(formatPaise(data.qr_paise), formatPaise(data.cash_paise))}</p>}
      </div>
      <button className="btn ghost" onClick={() => setCashOpen(true)}>{s.cash.button}</button>
      {loading && !data && <Loading />}
      {error && !data && <ErrorBox error={error} onRetry={reload} />}
      {data && (
        <>
          <div className="seg" role="tablist" aria-label={s.sales.title}>
            {(['people', 'all'] as const).map((v) => (
              <button key={v} type="button" role="tab" aria-selected={view === v} className={view === v ? 'on' : ''} onClick={() => setView(v)}>
                {v === 'people' ? s.sales.byPayer : s.sales.all}
              </button>
            ))}
          </div>

          {data.qr.length === 0 && data.cash.length === 0 && data.cash_unitemised_paise === 0 && <Empty text={s.sales.empty} />}

          <div className="list" aria-label={view === 'people' ? s.sales.byPayer : s.sales.all}>
            {view === 'people'
              ? data.by_payer.map((p) => (
                  <div key={`${p.channel}:${p.vpa ?? p.name}`} className="item payer">
                    <div className="row">
                      <span>{p.name}</span>
                      <span>{formatPaise(p.amount_paise)}</span>
                    </div>
                    <p className="sub">
                      <span className={'chip ' + (p.channel === 'qr' ? 'c-blue' : 'c-green')}>{p.channel === 'qr' ? 'QR' : 'Cash'}</span>
                      {p.vpa && <span>{p.vpa} · </span>}
                      {s.sales.payments(p.count)}
                    </p>
                  </div>
                ))
              : allPayments(data).map((r) => (
                  <div key={r.id} className="item payment">
                    <div className="row">
                      <span>{r.who}</span>
                      <span>{formatPaise(r.amount)}</span>
                    </div>
                    <p className="sub">
                      <span className={'chip ' + (r.channel === 'qr' ? 'c-blue' : 'c-green')}>{r.channel === 'qr' ? 'QR' : 'Cash'}</span>
                      {timeIST(r.ts)}{r.sub && <span> · {r.sub}</span>}
                    </p>
                  </div>
                ))}
            {data.cash_unitemised_paise > 0 && (
              <div className="item">
                <div className="row">
                  <span>{s.sales.unitemised(data.cash_source === 'logged')}</span>
                  <span>{formatPaise(data.cash_unitemised_paise)}</span>
                </div>
                <p className="sub"><span className="chip c-green">Cash</span></p>
              </div>
            )}
          </div>

          {data.udhaar_repaid.length > 0 && (
            <section className="card" aria-label={s.sales.repaidTitle}>
              <h2 className="mid">{s.sales.repaidTitle}</h2>
              <p className="sub">{s.sales.repaidNote}</p>
              {data.udhaar_repaid.map((u, i) => (
                <div key={`${u.customer_id}-${u.ts}-${i}`} className="row" style={{ marginTop: 8 }}>
                  <span>{u.customer_name} <span className="sub">· {timeIST(u.ts)}</span></span>
                  <b>{formatPaise(u.amount_paise)}</b>
                </div>
              ))}
            </section>
          )}
        </>
      )}
      {cashOpen && (
        <CashReceivedSheet
          onClose={() => setCashOpen(false)}
          onSaved={(m) => {
            setCashOpen(false);
            toast(m);
            reload();
          }}
        />
      )}
    </main>
  );
}
