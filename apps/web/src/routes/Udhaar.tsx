import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api, ApiError } from '../api/client';
import type { Customer, ReminderDraft } from '../api/types';
import { Empty, ErrorBox, Loading } from '../components/States';
import { useToast } from '../components/Toast';
import { shortDateTime } from '../lib/dates';
import { formatPaise } from '../lib/money';
import { useFetch } from '../lib/useFetch';
import { s } from '../strings';

function reasonText(r: string): string {
  return s.udhaar.skipped[r] ?? r;
}

function CustomerChips({ c }: { c: Customer }) {
  return (
    <div>
      {c.reminder.eligible && <span className="chip c-blue">{s.udhaar.ready}</span>}
      {!c.reminder.eligible && c.balance_paise > 0 && c.reminder.reason && <span className="chip c-grey">{reasonText(c.reminder.reason)}</span>}
      {c.late_payer && <span className="chip c-saf">{s.udhaar.lateChip}</span>}
      {c.last_payment_at && <span className="chip c-green">Last paid {shortDateTime(c.last_payment_at)}</span>}
    </div>
  );
}

export default function Udhaar() {
  const { data, error, loading, reload } = useFetch(api.customers, [], 4000);
  const [plans, setPlans] = useState<ReminderDraft[] | null>(null);
  const [planning, setPlanning] = useState(false);
  const [sent, setSent] = useState<Record<string, boolean>>({});
  const toast = useToast();

  const customers = data?.customers ?? [];
  const owing = customers.filter((c) => c.balance_paise > 0);
  const total = owing.reduce((a, c) => a + c.balance_paise, 0);
  const planByCustomer = new Map((plans ?? []).map((p) => [p.customer.id, p]));

  async function plan() {
    setPlanning(true);
    try {
      setPlans((await api.planReminders()).reminders);
    } catch (e) {
      toast(e instanceof ApiError ? e.message : s.common.genericError);
    } finally {
      setPlanning(false);
    }
  }

  async function send(r: ReminderDraft) {
    if (!r.wa_url) return;
    window.open(r.wa_url, '_blank', 'noopener');
    if (r.reminder_id) {
      try {
        await api.reminderSent(r.reminder_id);
      } catch {
        /* sending already happened in WhatsApp; marking is best effort */
      }
    }
    setSent((m) => ({ ...m, [r.customer.id]: true }));
  }

  return (
    <main className="screen">
      <div>
        <p className="sub">{s.udhaar.count(owing.length)}</p>
        <h1 className="h">{s.udhaar.title(formatPaise(total))}</h1>
      </div>
      {loading && !data && <Loading />}
      {error && !data && <ErrorBox error={error} onRetry={reload} />}
      {data && owing.length === 0 && <Empty text={s.udhaar.empty} />}
      {owing.length > 0 && (
        <>
          <div className="list">
            {owing.map((c) => {
              const p = planByCustomer.get(c.id);
              return (
                <div key={c.id} className="item">
                  <Link to={`/udhaar/${c.id}`} style={{ textDecoration: 'none', color: 'inherit', display: 'block' }}>
                    <div className="row"><span>{c.name}</span><span>{formatPaise(c.balance_paise)}</span></div>
                    <CustomerChips c={c} />
                  </Link>
                  {p && !p.skipped_reason && (
                    <div className="card stack" style={{ marginTop: 8, fontSize: 14 }}>
                      <p className="sub">{s.udhaar.draftFor(c.name)} · attempt {p.attempt}</p>
                      <p>{p.message}</p>
                      <button className="btn wa small" disabled={!p.wa_url} onClick={() => send(p)}>
                        {sent[c.id] ? `✓ ${s.udhaar.sent}` : s.udhaar.sendWa}
                      </button>
                      {p.payment_link && (
                        <a className="sub" href={p.payment_link.url} target="_blank" rel="noopener" style={{ textAlign: 'center', minHeight: 24 }}>
                          {s.udhaar.openLink}
                        </a>
                      )}
                    </div>
                  )}
                  {p?.skipped_reason && <span className="chip c-grey">{reasonText(p.skipped_reason)}</span>}
                </div>
              );
            })}
          </div>
          <button className="btn" disabled={planning} onClick={plan}>{planning ? s.udhaar.planning : s.udhaar.plan}</button>
        </>
      )}
    </main>
  );
}
