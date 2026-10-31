import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, ApiError } from '../api/client';
import { rupeesToPaise } from '../lib/money';
import { useSession } from '../session';
import { s } from '../strings';

export default function Onboarding() {
  const { merchant, setMerchant } = useSession();
  const [agree, setAgree] = useState(false);
  const [share, setShare] = useState(String(Math.round((merchant?.cash_share_estimate || 0.3) * 100)));
  const [cash, setCash] = useState(merchant?.cash_on_hand_paise ? String(merchant.cash_on_hand_paise / 100) : '');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const nav = useNavigate();

  const shareNum = Number(share) / 100;
  const cashPaise = cash.trim() === '' ? 0 : rupeesToPaise(cash);
  const valid = agree && shareNum > 0 && shareNum < 0.9 && cashPaise !== null;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!valid) return;
    setBusy(true);
    setErr(null);
    try {
      setMerchant(await api.consent({ data_use: true, cash_share_estimate: shareNum, cash_on_hand_paise: cashPaise ?? 0 }));
      nav('/', { replace: true });
    } catch (e2) {
      setErr(e2 instanceof ApiError ? e2.message : s.common.genericError);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="screen plain">
      <h1 className="h">{s.onboarding.title}</h1>
      <div className="card"><p style={{ fontSize: 15 }}>{s.onboarding.consentText}</p></div>
      <form className="form" onSubmit={submit}>
        <label className="check" style={{ color: 'var(--navy)' }}>
          <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} />
          <span>{s.onboarding.consentLabel}</span>
        </label>
        <label>{s.onboarding.cashShare}<input inputMode="numeric" value={share} onChange={(e) => setShare(e.target.value)} /></label>
        <label>{s.onboarding.cashOnHand}<input inputMode="decimal" value={cash} onChange={(e) => setCash(e.target.value)} /></label>
        {err && <p className="err" role="alert">{err}</p>}
        <button className="btn" disabled={!valid || busy}>{s.onboarding.submit}</button>
      </form>
    </main>
  );
}
