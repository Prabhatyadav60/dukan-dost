import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api, ApiError } from '../api/client';
import { CashReceivedSheet } from '../components/CashReceivedSheet';
import { ChatIcon } from '../components/Icons';
import { ErrorBox, Loading } from '../components/States';
import { useToast } from '../components/Toast';
import { shortDate, timeIST } from '../lib/dates';
import { formatPaise } from '../lib/money';
import { useFetch } from '../lib/useFetch';
import { useSession } from '../session';
import { s } from '../strings';

export default function Home() {
  const { merchant } = useSession();
  const { data, error, loading, reload } = useFetch(api.home, [], 10_000);
  const [paying, setPaying] = useState<string | null>(null);
  const [cashOpen, setCashOpen] = useState(false);
  const toast = useToast();

  async function markPaid(id: string) {
    setPaying(id);
    try {
      await api.markExpensePaid(id);
      toast(s.expense.marked);
      reload();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : s.common.genericError);
    } finally {
      setPaying(null);
    }
  }

  return (
    <>
      <div className="topbar">
        <span>{timeIST(new Date().toISOString())}</span>
        <Link to="/assistant" aria-label="Dukan Dost thread" style={{ color: 'var(--navy)', display: 'flex', gap: 6, alignItems: 'center', minHeight: 44 }}>
          <span>{merchant?.shop_name}</span><span style={{ width: 20, height: 20, display: 'inline-block' }}><ChatIcon /></span>
        </Link>
      </div>
      <main className="screen">
        <div>
          <p className="sub">{s.home.greeting(merchant?.owner_name ?? '')}</p>
          <h1 className="h">{s.home.title}</h1>
          <p className="tagline">
            {s.home.tagline} <span className="heart" aria-hidden="true">❤</span>
          </p>
        </div>
        {loading && !data && <Loading />}
        {error && !data && <ErrorBox error={error} onRetry={reload} />}
        {data && (
          <>
            <Link className="card dark link" to="/sales" aria-label={s.home.salesLink}>
              <p className="sub">{s.home.todaySales}</p>
              <p className="big">{formatPaise(data.sales.total_paise)}</p>
              <p className="sub">
                QR {formatPaise(data.sales.qr_paise)} · Cash {formatPaise(data.sales.cash_paise)} (
                {data.sales.cash_source === 'logged' ? s.home.cashLogged : s.home.cashEstimated})
              </p>
              <p className="sub more">{s.home.seeDetails}</p>
            </Link>
            <button className="btn ghost" onClick={() => setCashOpen(true)}>{s.cash.button}</button>
            <div className="split">
              <Link className="card link" to="/udhaar">
                <p className="sub">{s.home.udhaar}</p>
                <p className="mid">{formatPaise(data.udhaar_total_paise)}</p>
                <p className="sub">{s.home.customers(data.customers_with_balance)}</p>
              </Link>
              {data.restock_sections !== null ? (
                <Link className="card link" to="/scan">
                  <p className="sub">{s.home.restock}</p>
                  <p className="mid">{s.home.sections(data.restock_sections)}</p>
                </Link>
              ) : (
                <div className="card">
                  <p className="sub">{s.home.billsDue}</p>
                  <p className="mid">{data.bills_due.length ? formatPaise(data.bills_due.reduce((a, b) => a + b.total_paise, 0)) : '—'}</p>
                  <p className="sub">{data.bills_due.length ? `${data.bills_due.length} bill` : s.home.noBills}</p>
                </div>
              )}
            </div>
            {data.alert && (
              <Link className="alert" to="/forecast">
                <b>{data.alert.reason === 'bills' ? s.home.cashAlertTitle : s.home.alertTitle}</b>
                {data.alert.message}
              </Link>
            )}
            {data.bills_due.map((b) => (
              <div key={b.expense_id} className="billrow">
                <p className={b.overdue ? 'sub overdue' : 'sub'}>
                  {b.overdue ? s.home.overdue : s.home.dueSoon}: {b.vendor} {formatPaise(b.total_paise)} · {shortDate(b.due_date)}
                </p>
                <button className="btn ghost small" disabled={paying === b.expense_id} onClick={() => void markPaid(b.expense_id)}>
                  {s.expense.markPaid}
                </button>
              </div>
            ))}
            <p className="sub" style={{ textAlign: 'center', marginTop: 'auto' }}>{s.home.micHint}</p>
          </>
        )}
      </main>
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
    </>
  );
}
