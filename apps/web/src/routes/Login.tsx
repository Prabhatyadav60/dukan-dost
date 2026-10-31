import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, ApiError, setToken } from '../api/client';
import { useSession } from '../session';
import { s } from '../strings';

export default function Login() {
  const [phone, setPhone] = useState('+919999900001');
  const [otp, setOtp] = useState('123456');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const { setMerchant } = useSession();
  const nav = useNavigate();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const r = await api.login(phone.trim(), otp.trim());
      setToken(r.access_token);
      setMerchant(r.merchant);
      nav(r.merchant.consent_given ? '/' : '/onboarding', { replace: true });
    } catch (e2) {
      setErr(e2 instanceof ApiError && e2.code === 'invalid_otp' ? s.login.invalid : e2 instanceof ApiError ? e2.message : s.common.genericError);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="screen plain" style={{ justifyContent: 'center' }}>
      <p className="h" style={{ color: 'var(--saffron)' }}>{s.appName}</p>
      <h1 className="big">{s.login.title}</h1>
      <p className="sub">{s.login.sub}</p>
      <form className="form" onSubmit={submit} style={{ marginTop: 16 }}>
        <label>{s.login.phone}<input inputMode="tel" autoComplete="tel" value={phone} onChange={(e) => setPhone(e.target.value)} /></label>
        <label>{s.login.otp}<input inputMode="numeric" autoComplete="one-time-code" value={otp} onChange={(e) => setOtp(e.target.value)} /></label>
        {err && <p className="err" role="alert">{err}</p>}
        <button className="btn" disabled={busy}>{busy ? '…' : s.login.submit}</button>
      </form>
    </main>
  );
}
