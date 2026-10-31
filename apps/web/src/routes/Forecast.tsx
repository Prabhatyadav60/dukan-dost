import { useState } from 'react';
import { api } from '../api/client';
import { ForecastChart } from '../components/ForecastChart';
import { LoanCard } from '../components/LoanCard';
import { ErrorBox, Loading } from '../components/States';
import { shortDate } from '../lib/dates';
import { formatPaise } from '../lib/money';
import { useFetch } from '../lib/useFetch';
import { s } from '../strings';

export default function Forecast() {
  const f = useFetch(() => api.forecast(14), []);
  const loan = useFetch(api.loanOffer, [f.data?.forecast_id]);
  const [why, setWhy] = useState(false);
  const d = f.data;

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
              <div className="row warn"><b>{s.forecast.gap(d.buy_by_date ? shortDate(d.buy_by_date) : '—')}</b><b>{formatPaise(d.gap_paise)}</b></div>
            ) : (
              <p className="ok" style={{ marginTop: 6 }}>{s.forecast.noGap}</p>
            )}
          </div>
          {d.gap_paise > 0 && (
            <div className="card dark">
              <div className="row"><span>{s.forecast.collect}</span><b>{formatPaise(d.plan.collect_paise)}</b></div>
              {d.plan.loan_paise > 0 && <div className="row"><span>{s.forecast.loan}</span><b>{formatPaise(d.plan.loan_paise)}</b></div>}
              {d.plan.loan_paise > 0 && <p className="sub" style={{ marginTop: 6 }}>{s.forecast.disclaimer}</p>}
            </div>
          )}
          {d.explanation && <div className="bub hl" style={{ maxWidth: '100%' }}>{d.explanation}</div>}
          <button className="btn ghost small" onClick={() => setWhy((w) => !w)} aria-expanded={why}>{s.forecast.why}</button>
          {why && (
            <div className="card" style={{ fontSize: 13 }}>
              <p>Normal din ki bikri × tyohaar ka uplift = forecast.</p>
              <p>Extra bikri × (1 − margin {Math.round(d.assumptions.margin * 100)}%) = maal chahiye.</p>
              <p>Galle ka cash + wapas mila udhaar + margin − bills due (buy-by + {d.assumptions.dues_grace_days} din) = cash milega.</p>
              <p>Cash ka hissa: {Math.round(d.assumptions.cash_share * 100)}%.</p>
            </div>
          )}
          {loan.data && <LoanCard key={loan.data.offer_id} offer={loan.data} />}
        </>
      )}
    </main>
  );
}
