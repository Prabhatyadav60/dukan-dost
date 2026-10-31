import { useState } from 'react';
import { api, ApiError } from '../api/client';
import type { Customer } from '../api/types';
import { s } from '../strings';

/** Inline form used when a spoken name doesn't match any customer. */
export function NewCustomerForm({ initialName, onCreated }: { initialName: string; onCreated: (c: Customer) => void }) {
  const [name, setName] = useState(initialName);
  const [phone, setPhone] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setErr(null);
    const digits = phone.replace(/\D/g, '');
    const e164 = digits ? (digits.length === 10 ? `+91${digits}` : `+${digits}`) : null;
    try {
      onCreated(await api.createCustomer({ name: name.trim(), phone_e164: e164, aliases: [] }));
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : s.common.genericError);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card form">
      <b>{s.voice.newCustomerTitle}</b>
      <label>{s.voice.customer}<input value={name} onChange={(e) => setName(e.target.value)} /></label>
      <label>{s.voice.phone}<input inputMode="tel" placeholder="98xxxxxxxx" value={phone} onChange={(e) => setPhone(e.target.value)} /></label>
      {err && <p className="err">{err}</p>}
      <button className="btn small" disabled={busy || !name.trim()} onClick={submit}>{s.voice.addCustomer}</button>
    </div>
  );
}
