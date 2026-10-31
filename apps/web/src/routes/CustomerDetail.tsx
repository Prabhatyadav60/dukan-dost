import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, ApiError } from '../api/client';
import type { Customer } from '../api/types';
import { Empty, ErrorBox, Loading } from '../components/States';
import { useToast } from '../components/Toast';
import { shortDateTime } from '../lib/dates';
import { formatPaise } from '../lib/money';
import { useFetch } from '../lib/useFetch';
import { s } from '../strings';

export default function CustomerDetail() {
  const { id = '' } = useParams();
  const list = useFetch(api.customers, [], 4000);
  const entries = useFetch(() => api.customerEntries(id), [id], 4000);
  const c = list.data?.customers.find((x) => x.id === id) ?? null;
  const [phone, setPhone] = useState('');
  const toast = useToast();

  // optimistic: the box reflects the tap immediately, then follows the server once the list reloads
  const [dnr, setDnr] = useState<boolean | null>(null);
  useEffect(() => setDnr(null), [c?.do_not_remind]);

  useEffect(() => {
    if (c) setPhone(c.phone_e164 ?? '');
    // only when the customer first loads
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [c?.id]);

  async function patch(b: Parameters<typeof api.patchCustomer>[1]): Promise<Customer | null> {
    try {
      const r = await api.patchCustomer(id, b);
      list.reload();
      toast('Save ho gaya');
      return r;
    } catch (e) {
      toast(e instanceof ApiError ? e.message : s.common.genericError);
      return null;
    }
  }

  if (list.loading && !list.data) return <main className="screen"><Loading /></main>;
  if (list.error && !list.data) return <main className="screen"><ErrorBox error={list.error} onRetry={list.reload} /></main>;
  if (!c) return <main className="screen"><Empty text="Customer nahi mila" action={<Link to="/udhaar">{s.common.back}</Link>} /></main>;

  return (
    <main className="screen">
      <Link to="/udhaar" className="sub" style={{ minHeight: 24 }}>← {s.common.back}</Link>
      <div>
        <h1 className="h">{c.name}</h1>
        <p className="big">{formatPaise(c.balance_paise)}</p>
        {c.late_payer && <span className="chip c-saf">{s.udhaar.lateChip}</span>}
      </div>
      <div className="card form">
        <label>{s.customer.phone}
          <div className="textrow">
            <input inputMode="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+9198xxxxxxxx" />
            <button className="btn small" onClick={() => {
              const d = phone.replace(/\D/g, '');
              void patch({ phone_e164: d ? (d.length === 10 ? `+91${d}` : `+${d}`) : null });
            }}>{s.customer.savePhone}</button>
          </div>
        </label>
        <label className="check" style={{ color: 'var(--navy)' }}>
          <input type="checkbox" checked={dnr ?? c.do_not_remind} onChange={(e) => {
            const v = e.target.checked;
            setDnr(v);
            void patch({ do_not_remind: v }).then((r) => { if (!r) setDnr(null); });
          }} />
          <span>{s.customer.dnr}</span>
        </label>
      </div>
      <h2 className="mid">{s.customer.entries}</h2>
      {entries.loading && !entries.data && <Loading blocks={2} />}
      {entries.data && entries.data.entries.length === 0 && <Empty text={s.customer.noEntries} />}
      <div className="list">
        {entries.data?.entries.map((e) => (
          <div key={e.id} className="item">
            <div className="row">
              <span>{shortDateTime(e.created_at)} · {e.type === 'credit' ? s.customer.credit : s.customer.payment}</span>
              <span style={{ color: e.type === 'payment' ? 'var(--success)' : undefined }}>
                {e.type === 'payment' ? '−' : '+'}{formatPaise(e.amount_paise)}
              </span>
            </div>
            <p className="sub">{[e.items.join(', '), e.source === 'pay_link' ? s.customer.viaLink : e.source].filter(Boolean).join(' · ')}</p>
          </div>
        ))}
      </div>
    </main>
  );
}
