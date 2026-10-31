import { useEffect, useState } from 'react';
import { api, ApiError } from '../api/client';
import type { CashReceiptKind, Customer } from '../api/types';
import { newIdempotencyKey } from '../lib/idempotency';
import { formatPaise, rupeesToPaise } from '../lib/money';
import { s } from '../strings';

interface Props {
  onClose: () => void;
  /** Called with the toast text after a successful save. */
  onSaved: (message: string) => void;
}

/** "Cash mila": a cash sale (adds to today's cash) or udhaar paid back in cash (reduces a balance). */
export function CashReceivedSheet({ onClose, onSaved }: Props) {
  const [key] = useState(newIdempotencyKey);
  const [amount, setAmount] = useState('');
  const [kind, setKind] = useState<CashReceiptKind>('sale');
  const [customerId, setCustomerId] = useState('');
  const [note, setNote] = useState('');
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.customers().then((r) => setCustomers(r.customers)).catch(() => {});
  }, []);

  const amountPaise = rupeesToPaise(amount);
  const canSave = !!amountPaise && !busy && (kind === 'sale' || !!customerId);

  async function save() {
    if (!amountPaise) return;
    setBusy(true);
    setErr(null);
    try {
      const r = await api.cashReceipt(
        {
          amount_paise: amountPaise,
          kind,
          ...(kind === 'udhaar' ? { customer_id: customerId } : {}),
          ...(note.trim() ? { note: note.trim() } : {}),
        },
        key,
      );
      const amt = formatPaise(r.receipt.amount_paise);
      onSaved(kind === 'sale' ? s.cash.savedSale(amt) : s.cash.savedUdhaar(r.receipt.customer_name ?? r.customer?.name ?? '', amt));
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : s.common.genericError);
      setBusy(false);
    }
  }

  return (
    <div className="dim" onClick={onClose}>
      <div className="sheet" role="dialog" aria-modal="true" aria-label={s.cash.title} onClick={(e) => e.stopPropagation()}>
        <div className="grab" />
        <h2 className="h" style={{ fontSize: 21 }}>{s.cash.title}</h2>
        <div className="field">
          <span>{s.cash.amount}</span>
          <input autoFocus inputMode="decimal" aria-label={s.cash.amount} value={amount} onChange={(e) => setAmount(e.target.value)} style={{ fontWeight: 700 }} />
        </div>
        <p className="sub">{s.cash.kindQuestion}</p>
        <div className="seg" role="radiogroup" aria-label={s.cash.kindQuestion}>
          {(['sale', 'udhaar'] as const).map((k) => (
            <button key={k} type="button" role="radio" aria-checked={kind === k} className={kind === k ? 'on' : ''} onClick={() => setKind(k)}>
              {k === 'sale' ? s.cash.sale : s.cash.udhaar}
            </button>
          ))}
        </div>
        {kind === 'udhaar' && (
          <div className="field">
            <span>{s.cash.customer}</span>
            <select aria-label={s.cash.customer} value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
              <option value="" disabled>{s.cash.pickCustomer}</option>
              {customers.map((c) => (
                <option key={c.id} value={c.id}>{c.name} · {formatPaise(c.balance_paise)}</option>
              ))}
            </select>
          </div>
        )}
        <div className="field">
          <span>{s.cash.note}</span>
          <input aria-label={s.cash.note} maxLength={80} placeholder={s.cash.notePlaceholder} value={note} onChange={(e) => setNote(e.target.value)} />
        </div>
        {err && <p className="err" role="alert">{err}</p>}
        <div className="btns" style={{ marginTop: 6 }}>
          <button className="btn ghost" onClick={onClose}>{s.common.cancel}</button>
          <button className="btn" disabled={!canSave} onClick={save}>{busy ? '…' : s.cash.save}</button>
        </div>
      </div>
    </div>
  );
}
