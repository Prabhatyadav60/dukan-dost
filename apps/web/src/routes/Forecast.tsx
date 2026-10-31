import { useState } from 'react';
import { api, ApiError } from '../api/client';
import { ForecastChart } from '../components/ForecastChart';
import { LoanCard } from '../components/LoanCard';
import { ErrorBox, Loading } from '../components/States';
import { useToast } from '../components/Toast';
import { shortDate } from '../lib/dates';
import { formatPaise } from '../lib/money';
import { useFetch } from '../lib/useFetch';
import { s } from '../strings';

export default function Forecast() {
  const f = useFetch(() => api.forecast(14), []);
  const loan = useFetch(api.loanOffer, [f.data?.forecast_id]);
  const [why, setWhy] = useState(false);
  const [paying, setPaying] = useState<string | null>(null);
  const toast = useToast();
  const d = f.data;
  const shortfallBy = d?.shortfall_date ?? d?.buy_by_date ?? null;

  async function markPaid(id: string) {
    setPaying(id);
    try {
      await api.markExpensePaid(id);
      toast(s.expense.marked);
      f.reload(); // loan offer refetches when the new forecast id arrives
    } catch (e) {
      toast(e instanceof ApiError ? e.message : s.common.genericError);
    } finally {
      setPaying(null);
    }
  }

  return (
    <main className="screen">
      <div>
        <p className="sub">{s.forecast.sub}</p>
        <h1 className="h">{s.forecast.title(d?.festival?.name ?? null)}</h1>
      </div>
      {f.loading && !d && <Loading />}
      {f.error && !d && <ErrorBox error={f.error} onRetry={f.reload} />}
      {d && (
        <>
          <ForecastChart f={d} />
          <div className="card">
            <div className="row"><span>{s.forecast.needed}</span><b>{formatPaise(d.stock_needed_paise)}</b></div>
            <div className="row"><span>{s.forecast.available}</span><b>{formatPaise(d.cash_available_paise)}</b></div>
            {d.gap_paise > 0 ? (
              <div className="row warn"><b>{s.forecast.gap(shortfallBy ? shortDate(shortfallBy) : '—')}</b><b>{formatPaise(d.gap_paise)}</b></div>
            ) : (
              <p className="ok" style={{ marginTop: 6 }}>{s.forecast.noGap}</p>
            )}
          </div>
          {(d.gap_paise > 0 || d.plan.loan_paise > 0) && (
            <div className="card dark">
              <div className="row"><span>{s.forecast.collect}</span><b>{formatPaise(d.plan.collect_paise)}</b></div>
              {d.plan.loan_paise > 0 && <div className="row"><span>{s.forecast.loan}</span><b>{formatPaise(d.plan.loan_paise)}</b></div>}
              {d.plan.loan_paise > 0 && <p className="sub" style={{ marginTop: 6 }}>{s.forecast.disclaimer}</p>}
            </div>
          )}
          {d.explanation && <div className="bub hl" style={{ maxWidth: '100%' }}>{d.explanation}</div>}
          {d.timeline && d.timeline.length > 0 && (
            <section className="card" aria-label={s.forecast.timeline}>
              <h2 className="mid">{s.forecast.timeline}</h2>
              <p className="sub" style={{ marginBottom: 4 }}>{s.forecast.timelineSub}</p>
              {d.timeline.map((day) => {
                const low = d.low_point?.date === day.date;
                return (
                  <div key={day.date} className={'tl-day' + (low ? ' low' : '') + (low && day.balance_paise < 0 ? ' neg' : '')}>
                    <div className="row">
                      <b>{shortDate(day.date)}{low && <span className="sub"> · {s.forecast.lowPoint}</span>}</b>
                      <span>
                        <span className="sub">{s.forecast.balance} </span>
                        <b className={day.balance_paise < 0 ? 'bal-neg' : ''}>{formatPaise(day.balance_paise)}</b>
                      </span>
                    </div>
                    {day.events.map((ev, i) => (
                      <div key={i} className="ev">
                        <span>{ev.label}</span>
                        <span className={ev.amount_paise < 0 ? 'amt-out' : 'amt-in'}>
                          {ev.amount_paise < 0 ? '−' : '+'}{formatPaise(Math.abs(ev.amount_paise))}
                        </span>
                      </div>
                    ))}
                  </div>
                );
              })}
            </section>
          )}
          {d.bills && (
            <div className="card">
              <p className="sub" style={{ marginBottom: 4 }}>{s.forecast.bills}</p>
              {d.bills.length === 0 && <p className="ok">{s.forecast.noBills}</p>}
              {d.bills.map((b) => (
                <div key={b.id} className="billrow">
                  <div>
                    <b>{b.vendor}</b> · {formatPaise(b.total_paise)}
                    {b.due_date && <p className={b.overdue ? 'sub overdue' : 'sub'}>{s.forecast.due} {shortDate(b.due_date)}</p>}
                    <p>
                      {b.overdue && <span className="chip c-red">{s.forecast.overdue}</span>}
                      {b.counted && <span className="chip c-blue">{s.forecast.counted}</span>}
                    </p>
                  </div>
                  <button className="btn ghost small" disabled={paying === b.id} onClick={() => void markPaid(b.id)}>{s.expense.paid}</button>
                </div>
              ))}
            </div>
          )}
          <button className="btn ghost small" onClick={() => setWhy((w) => !w)} aria-expanded={why}>{s.forecast.why}</button>
          {why && (
            <div className="card" style={{ fontSize: 13 }}>
              <p>Normal din ki bikri × tyohaar ka uplift = forecast.</p>
              <p>Extra bikri × (1 − margin {Math.round(d.assumptions.margin * 100)}%) = maal chahiye.</p>
              {d.breakdown ? (
                <div style={{ margin: '6px 0' }}>
                  <div className="row"><span>{s.forecast.onHand}</span><span>{formatPaise(d.breakdown.cash_on_hand_paise)}</span></div>
                  <div className="row"><span>+ {s.forecast.received}</span><span>{formatPaise(d.breakdown.received_paise)}</span></div>
                  <div className="row"><span>+ {s.forecast.profit}</span><span>{formatPaise(d.breakdown.profit_to_buy_paise)}</span></div>
                  <div className="row"><span>− {s.forecast.dues}</span><span>{formatPaise(d.breakdown.dues_paise)}</span></div>
                  <div className="row"><span>− {s.forecast.spent}</span><span>{formatPaise(d.breakdown.spent_paise)}</span></div>
                  <div className="row total"><b>= {s.forecast.equals}</b><b>{formatPaise(d.cash_available_paise)}</b></div>
                </div>
              ) : (
                <p>Galle ka cash + wapas mila udhaar + margin − bills due = cash milega.</p>
              )}
              <p>Cash ka hissa: {Math.round(d.assumptions.cash_share * 100)}%.</p>
            </div>
          )}
          {loan.data && <LoanCard key={loan.data.offer_id} offer={loan.data} />}
        </>
      )}
    </main>
  );
}
