import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, ApiError } from '../api/client';
import type { BillScanResponse, ShelfScan } from '../api/types';
import { BillReviewSheet } from '../components/BillReviewSheet';
import { ErrorBox, Loading } from '../components/States';
import { useToast } from '../components/Toast';
import { shortDate } from '../lib/dates';
import { resizeImage } from '../lib/resizeImage';
import { useFetch } from '../lib/useFetch';
import { s } from '../strings';

type Tab = 'bill' | 'shelf';

export default function Scan() {
  const [tab, setTab] = useState<Tab>('bill');
  return (
    <main className="screen">
      <div className="seg" role="tablist" aria-label="Scan">
        {(['bill', 'shelf'] as const).map((t) => (
          <button key={t} type="button" role="tab" aria-selected={tab === t} className={tab === t ? 'on' : ''} onClick={() => setTab(t)}>
            {t === 'bill' ? s.scan.tabBill : s.scan.tabShelf}
          </button>
        ))}
      </div>
      {tab === 'bill' ? <BillTab /> : <ShelfTab />}
    </main>
  );
}

type Phase = 'pick' | 'reading' | 'review';

function BillTab() {
  const [phase, setPhase] = useState<Phase>('pick');
  const [previews, setPreviews] = useState<string[]>([]);
  const [scan, setScan] = useState<BillScanResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
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
      setScan(await api.scanBill(blobs));
    } catch (e) {
      setScan(null);
      setErr(e instanceof ApiError && e.code === 'network' ? s.common.networkError : s.scan.failed);
    }
    setAttempt((n) => n + 1); // fresh review form (and idempotency key) per scan
    setPhase('review');
  }

  return (
    <>
      <div>
        <p className="sub">{phase === 'review' && previews.length ? s.scan.pages(previews.length) : s.scan.sub}</p>
        <h1 className="h">{phase === 'review' && scan?.draft.vendor ? scan.draft.vendor : s.scan.title}</h1>
      </div>
      <input ref={input} type="file" accept="image/*" capture="environment" multiple hidden onChange={(e) => { void onFiles(e.target.files); e.target.value = ''; }} />

      {previews.length > 0 && <div className="thumbs">{previews.map((u) => <img key={u} src={u} alt="Bill page" />)}</div>}

      {phase === 'pick' && (
        <div className="stack" style={{ marginTop: 24 }}>
          <button className="btn" onClick={() => input.current?.click()}>{s.scan.pick}</button>
          <button className="btn ghost" onClick={() => { setScan(null); setErr(null); setAttempt((n) => n + 1); setPhase('review'); }}>{s.scan.manual}</button>
        </div>
      )}
      {phase === 'reading' && <div className="skel" style={{ height: 220 }} role="status" aria-label={s.scan.reading} />}
      {phase === 'reading' && <p className="sub" style={{ textAlign: 'center' }}>{s.scan.reading}</p>}

      {phase === 'review' && (
        <BillReviewSheet
          key={attempt}
          scan={scan}
          error={err}
          onRetake={() => input.current?.click()}
          onSaved={(m) => {
            toast(m);
            nav('/assistant');
          }}
        />
      )}
    </>
  );
}

function ShelfTab() {
  const latest = useFetch(() => api.shelfLatest('main'), []);
  const [result, setResult] = useState<ShelfScan | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [reading, setReading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  async function onFile(files: FileList | null) {
    const f = files?.[0];
    if (!f) return;
    setPreview(URL.createObjectURL(f));
    setErr(null);
    setReading(true);
    try {
      setResult(await api.shelfScan(await resizeImage(f), 'main'));
    } catch (e) {
      setErr(e instanceof ApiError && e.code !== 'network' ? e.message || s.shelf.failed : s.common.networkError);
    } finally {
      setReading(false);
    }
  }

  const shown = result ?? latest.data;

  return (
    <>
      <div>
        <p className="sub">{s.shelf.sub}</p>
        <h1 className="h">{s.shelf.title}</h1>
      </div>
      <input ref={input} type="file" accept="image/*" capture="environment" hidden onChange={(e) => { void onFile(e.target.files); e.target.value = ''; }} />
      {preview && <div className="thumbs"><img src={preview} alt="Shelf" /></div>}

      {reading && <div className="skel" style={{ height: 160 }} role="status" aria-label={s.shelf.reading} />}
      {reading && <p className="sub" style={{ textAlign: 'center' }}>{s.shelf.reading}</p>}
      {err && <p className="err" role="alert">{err}</p>}

      {!reading && latest.loading && !latest.data && !result && <Loading blocks={2} />}
      {!reading && latest.error && !result && <ErrorBox error={latest.error} onRetry={latest.reload} />}
      {!reading && !shown && !latest.loading && !latest.error && <p className="sub">{s.shelf.none}</p>}

      {!reading && shown && <ShelfResult scan={shown} />}

      <button className="btn" style={{ marginTop: 8 }} disabled={reading} onClick={() => input.current?.click()}>
        {shown ? s.shelf.retake : s.shelf.pick}
      </button>
    </>
  );
}

function ShelfResult({ scan }: { scan: ShelfScan }) {
  const restock = scan.findings.filter((f) => f.status === 'restock');
  const tips = scan.findings.filter((f) => f.status === 'tip');
  return (
    <div className="stack" style={{ gap: 10 }}>
      {scan.first_scan ? (
        <div>
          <h2 className="mid">{s.shelf.firstTitle}</h2>
          <p className="sub">{s.shelf.firstNote}</p>
        </div>
      ) : (
        <div>
          <h2 className="mid">{s.shelf.compared(scan.compared_with_dates.length)}</h2>
          {scan.compared_with_dates.length > 0 && <p className="sub">{scan.compared_with_dates.map(shortDate).join(' · ')}</p>}
          {!scan.comparable && <p className="warn-text">{s.shelf.notComparable}</p>}
        </div>
      )}
      {scan.findings.length === 0 && <p className="ok">{s.shelf.noFindings}</p>}
      {restock.map((f, i) => (
        <div key={`r${i}`} className="alert"><b>{f.section} · {s.shelf.restock}</b>{f.note}</div>
      ))}
      {tips.map((f, i) => (
        <div key={`t${i}`} className="tipcard"><b>{s.shelf.tip} · {f.section}</b>{f.note}</div>
      ))}
    </div>
  );
}
