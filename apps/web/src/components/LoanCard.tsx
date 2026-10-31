import { useState } from 'react';
import { api, ApiError } from '../api/client';
import type { LoanOffer } from '../api/types';
import { formatPaise } from '../lib/money';
import { s } from '../strings';
import { useToast } from './Toast';

export function LoanCard({ offer }: { offer: LoanOffer }) {
  const [o, setO] = useState(offer);
  const [busy, setBusy] = useState(false);
  const toast = useToast();

  async function interest() {
    setBusy(true);
    try {
      setO(await api.loanInterest(o.offer_id));
    } catch (e) {
      toast(e instanceof ApiError ? e.message : s.common.genericError);
    } finally {
      setBusy(false);
    }
  }

  if (o.status === 'interested') {
    return <div className="card" style={{ background: 'var(--success-soft)', border: 'none' }}><p className="ok">✓ {s.forecast.interested}</p><p className="sub">{formatPaise(o.amount_paise)} · {o.disclaimer}</p></div>;
  }
  return (
    <button className="btn brand" disabled={busy} onClick={interest}>
      {s.forecast.seeLoan} · {formatPaise(o.amount_paise)}
    </button>
  );
}
