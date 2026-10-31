import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, ApiError } from '../api/client';
import type { BillScanResponse, LineItem } from '../api/types';
import { useToast } from '../components/Toast';
import { newIdempotencyKey } from '../lib/idempotency';
import { formatPaise, paiseToRupeesInput, rupeesToPaise } from '../lib/money';
import { resizeImage } from '../lib/resizeImage';
import { s } from '../strings';

type Phase = 'pick' | 'reading' | 'review';

export default function Scan() {
  const [phase, setPhase] = useState<Phase>('pick');
  const [previews, setPreviews] = useState<string[]>([]);
  const [scan, setScan] = useState<BillScanResponse | null>(null);
  const [vendor, setVendor] = useState('');
  const [total, setTotal] = useState('');
  const [due, setDue] = useState('');
  const [lines, setLines] = useState<LineItem[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [key, setKey] = useState(newIdempotencyKey);
  const input = useRef<HTMLInputElement>(null);
  const toast = useToast();
  const nav = useNavigate();

  useEffect(() => () => previews.forEach(URL.revokeObjectURL), [previews]);

  async function onFiles(files: FileList | null) {
    if (!files?.length) return;
    const list = Array.from(files).slice(0, 3);
    setPreviews(list.map((f) => URL.createObjectURL(f)));
    setErr(null);
    setPhase('reading');
    try {
      const blobs = await Promise.all(list.map((f) => resizeImage(f)));
      const r = await api.scanBill(blobs);
      setScan(r);
      setVendor(r.draft.vendor ?? '');
      setTotal(r.draft.total_paise ? paiseToRupeesInput(r.draft.total_paise) : '');
      setDue(r.draft.due_date ?? '');
      setLines(r.draft.line_items);
    } catch (e) {
      setScan(null);
      setLines([]);
      setErr(e instanceof ApiError && e.code === 'network' ? s.common.networkError : s.scan.failed);
    }
    setKey(newIdempotencyKey());
    setPhase('review');
  }

  const totalPaise = rupeesToPaise(total);
  const lineSum = lines.reduce((a, l) => a + l.amount_paise, 0);
  const diff = totalPaise !== null ? lineSum - totalPaise : 0;
  const hasLines = lines.length > 0;
  const sumOk = !hasLines || (totalPaise !== null && Math.abs(diff) <= Math.max(100, Math.round(totalPaise * 0.01)));

  async function save(force: boolean) {
    if (!totalPaise || !vendor.trim() || (!sumOk && !force)) return;
    setBusy(true);
    try {
      await api.createExpense(
        { vendor: vendor.trim(), line_items: lines, total_paise: totalPaise, due_date: due || null, category: 'stock',
          source: scan ? 'bill_scan' : 'manual', image_keys: scan?.image_keys ?? [] },
        key,
      );
      toast(`${s.scan.saved}: ${formatPaise(totalPaise)}`);
      nav('/assistant');
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : s.common.genericError);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="screen">
      <div>
        <p className="sub">{phase === 'review' && previews.length ? s.scan.pages(previews.length) : s.scan.sub}</p>
        <h1 className="h">{phase === 'review' && vendor ? vendor : s.scan.title}</h1>
      </div>
      <input ref={input} type="file" accept="image/*" capture="environment" multiple hidden onChange={(e) => { void onFiles(e.target.files); e.target.value = ''; }} />

      {previews.length > 0 && <div className="thumbs">{previews.map((u) => <img key={u} src={u} alt="Bill page" />)}</div>}

      {phase === 'pick' && (
        <div className="stack" style={{ marginTop: 24 }}>
          <button className="btn" onClick={() => input.current?.click()}>{s.scan.pick}</button>
          <button className="btn ghost" onClick={() => { setPhase('review'); setScan(null); setLines([]); }}>{s.scan.manual}</button>
        </div>
      )}
      {phase === 'reading' && <div className="skel" style={{ height: 220 }} role="status" aria-label={s.scan.reading} />}
      {phase === 'reading' && <p className="sub" style={{ textAlign: 'center' }}>{s.scan.reading}</p>}

      {phase === 'review' && (
        <>
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
          {scan?.draft.unreadable_fields.length ? <p className="warn-text">Padh nahi paaya: {scan.draft.unreadable_fields.join(', ')}</p> : null}
          <div className="field"><span>{s.scan.vendor}</span><input value={vendor} onChange={(e) => setVendor(e.target.value)} /></div>
          <div className="field"><span>{s.scan.total} (₹)</span><input inputMode="decimal" value={total} onChange={(e) => setTotal(e.target.value)} style={{ fontWeight: 700 }} /></div>
          <div className="field"><span>{s.scan.due}</span><input type="date" value={due} onChange={(e) => setDue(e.target.value)} style={{ color: 'var(--saffron-ink)', fontWeight: 700 }} /></div>
          <div className="btns" style={{ marginTop: 8 }}>
            <button className="btn ghost" onClick={() => input.current?.click()}>{s.common.edit}</button>
            {sumOk ? (
              <button className="btn" disabled={busy || !totalPaise || !vendor.trim()} onClick={() => save(false)}>{s.scan.save}</button>
            ) : (
              <button className="btn saffron" disabled={busy || !totalPaise || !vendor.trim()} onClick={() => save(true)}>{s.scan.saveAnyway}</button>
            )}
          </div>
        </>
      )}
    </main>
  );
}
