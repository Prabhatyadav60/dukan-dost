import { useState } from 'react';
import { api, ApiError } from '../api/client';
import type { BillScanResponse, ExpenseStatus, LineItem } from '../api/types';
import { newIdempotencyKey } from '../lib/idempotency';
import { formatPaise, paiseToRupeesInput, rupeesToPaise } from '../lib/money';
import { s } from '../strings';
import { PaidChoice } from './PaidChoice';

interface Props {
  /** null = manual entry (scan failed or skipped). */
  scan: BillScanResponse | null;
  error?: string | null;
  /** Render as a bottom sheet (chat) or inline in a page (Scan tab). */
  asSheet?: boolean;
  onRetake?: () => void;
  onClose?: () => void;
  onSaved: (message: string) => void;
}

/** Review an extracted bill: our own sum check, paid-or-due choice, then save as an expense. */
export function BillReviewSheet({ scan, error, asSheet, onRetake, onClose, onSaved }: Props) {
  const d = scan?.draft;
  const [vendor, setVendor] = useState(d?.vendor ?? '');
  const [total, setTotal] = useState(d?.total_paise ? paiseToRupeesInput(d.total_paise) : '');
  const [due, setDue] = useState(d?.due_date ?? '');
  const [status, setStatus] = useState<ExpenseStatus | null>(null);
  const [lines] = useState<LineItem[]>(d?.line_items ?? []);
  const [err, setErr] = useState<string | null>(error ?? null);
  const [busy, setBusy] = useState(false);
  const [key] = useState(newIdempotencyKey);

  const totalPaise = rupeesToPaise(total);
  const lineSum = lines.reduce((a, l) => a + l.amount_paise, 0);
  const diff = totalPaise !== null ? lineSum - totalPaise : 0;
  const hasLines = lines.length > 0;
  const sumOk = !hasLines || (totalPaise !== null && Math.abs(diff) <= Math.max(100, Math.round(totalPaise * 0.01)));
  const ready = !busy && !!totalPaise && !!vendor.trim() && status !== null;

  async function save(force: boolean) {
    if (!ready || !totalPaise || !status || (!sumOk && !force)) return;
    setBusy(true);
    setErr(null);
    try {
      await api.createExpense(
        { vendor: vendor.trim(), line_items: lines, total_paise: totalPaise,
          due_date: status === 'unpaid' ? due || null : null, category: 'stock',
          source: scan ? 'bill_scan' : 'manual', image_keys: scan?.image_keys ?? [], status },
        key,
      );
      onSaved(`${s.scan.saved}: ${formatPaise(totalPaise)}`);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : s.common.genericError);
      setBusy(false);
    }
  }

  const body = (
    <>
      {asSheet && <div className="grab" />}
      {asSheet && <h2 className="h" style={{ fontSize: 21 }}>{vendor || s.scan.title}</h2>}
      {err && <p className="err" role="alert">{err}</p>}
      {hasLines && (
        <div className="card">
          {lines.map((l, i) => (
            <div className="row" key={i}>
              <span>{l.name}{l.qty ? ` ×${l.qty}` : ''}</span><span>{formatPaise(l.amount_paise)}</span>
            </div>
          ))}
          <div className="row total"><span>{s.scan.total}</span><span>{totalPaise ? formatPaise(totalPaise) : '—'}</span></div>
        </div>
      )}
      {hasLines && (sumOk ? <p className="ok">{s.scan.sumOk}</p> : <p className="warn-text">{s.scan.sumBad(formatPaise(Math.abs(diff)))}</p>)}
      {d?.unreadable_fields.length ? <p className="warn-text">Padh nahi paaya: {d.unreadable_fields.join(', ')}</p> : null}
      <div className="field"><span>{s.scan.vendor}</span><input value={vendor} onChange={(e) => setVendor(e.target.value)} /></div>
      <div className="field"><span>{s.scan.total} (₹)</span><input inputMode="decimal" value={total} onChange={(e) => setTotal(e.target.value)} style={{ fontWeight: 700 }} /></div>
      <PaidChoice value={status} onChange={setStatus} />
      {status === 'unpaid' && (
        <div className="field"><span>{s.expense.dueDate}</span><input type="date" aria-label={s.expense.dueDate} value={due} onChange={(e) => setDue(e.target.value)} style={{ color: 'var(--saffron-ink)', fontWeight: 700 }} /></div>
      )}
      <div className="btns" style={{ marginTop: 8 }}>
        {onRetake ? <button className="btn ghost" onClick={onRetake}>{s.common.edit}</button>
          : <button className="btn ghost" onClick={onClose}>{s.common.cancel}</button>}
        {sumOk ? (
          <button className="btn" disabled={!ready} onClick={() => save(false)}>{s.scan.save}</button>
        ) : (
          <button className="btn saffron" disabled={!ready} onClick={() => save(true)}>{s.scan.saveAnyway}</button>
        )}
      </div>
    </>
  );

  if (!asSheet) return body;
  return (
    <div className="dim" onClick={onClose}>
      <div className="sheet" role="dialog" aria-modal="true" aria-label={s.scan.title} onClick={(e) => e.stopPropagation()}>
        {body}
      </div>
    </div>
  );
}
