import { useEffect, useMemo, useState } from 'react';
import { api, ApiError } from '../api/client';
import type { Customer, ExpenseCategory, ExpenseStatus, Intent, VoiceParseResponse } from '../api/types';
import { todayIST } from '../lib/dates';
import { newIdempotencyKey } from '../lib/idempotency';
import { formatPaise, paiseToRupeesInput, rupeesToPaise } from '../lib/money';
import { s } from '../strings';
import { NewCustomerForm } from './NewCustomerForm';
import { PaidChoice } from './PaidChoice';

const NEW = '__new__';

interface Props {
  /** null = manual entry (AI unavailable). */
  parsed: VoiceParseResponse | null;
  source: 'voice' | 'text' | 'manual';
  onClose: () => void;
  onSaved: (message: string) => void;
}

export function ConfirmSheet({ parsed, source, onClose, onSaved }: Props) {
  const draft = parsed?.draft ?? null;
  const match = parsed?.customer_match ?? null;
  const [key] = useState(newIdempotencyKey);
  const [intent, setIntent] = useState<Intent>(draft?.intent ?? 'credit');
  const [amount, setAmount] = useState(draft?.amount_paise ? paiseToRupeesInput(draft.amount_paise) : '');
  const [items, setItems] = useState((draft?.items ?? []).join(', '));
  const [vendor, setVendor] = useState(draft?.vendor ?? '');
  const [category, setCategory] = useState<ExpenseCategory>(draft?.category ?? 'other');
  const [expStatus, setExpStatus] = useState<ExpenseStatus | null>(draft?.expense_status ?? null);
  const [due, setDue] = useState(draft?.due_date ?? '');
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [customerId, setCustomerId] = useState<string>(
    match?.status === 'matched' && match.customer_id ? match.customer_id : match?.status === 'new' ? NEW : '',
  );
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.customers().then((r) => setCustomers(r.customers)).catch(() => {});
  }, []);

  const needsCustomer = intent === 'credit' || intent === 'payment';
  const amountPaise = rupeesToPaise(amount);
  const selected = customers.find((c) => c.id === customerId);
  const newTotal = useMemo(() => {
    if (!selected || !amountPaise) return null;
    return selected.balance_paise + (intent === 'credit' ? amountPaise : -amountPaise);
  }, [selected, amountPaise, intent]);

  const itemList = items.split(',').map((x) => x.trim()).filter(Boolean);
  const canSave =
    !!amountPaise && !busy && (!needsCustomer || (!!customerId && customerId !== NEW)) && (intent !== 'expense' || (!!vendor.trim() && expStatus !== null));

  async function save() {
    if (!amountPaise) return;
    setBusy(true);
    setErr(null);
    const src = source === 'manual' ? 'manual' : source;
    try {
      if (intent === 'credit' || intent === 'payment') {
        const r = await api.createEntry(
          { customer_id: customerId, type: intent, amount_paise: amountPaise, items: itemList, source: src,
            transcript: parsed?.transcript ?? null },
          key,
        );
        onSaved(`Likh diya. ${r.customer.name} ka total ab ${formatPaise(r.customer.balance_paise)}.`);
      } else if (intent === 'expense') {
        await api.createExpense(
          { vendor: vendor.trim(), line_items: [], total_paise: amountPaise,
            due_date: expStatus === 'unpaid' ? due || null : null, category, source: src, image_keys: [],
            status: expStatus ?? 'paid' },
          key,
        );
        onSaved(`Kharcha likh diya: ${formatPaise(amountPaise)}`);
      } else {
        await api.cashLog({ date: todayIST(), amount_paise: amountPaise, source: src }, key);
        onSaved(`Aaj ki cash bikri: ${formatPaise(amountPaise)}`);
      }
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : s.common.genericError);
      setBusy(false);
    }
  }

  return (
    <div className="dim" onClick={onClose}>
      <div className="sheet" role="dialog" aria-modal="true" aria-label={s.voice.confirmTitle} onClick={(e) => e.stopPropagation()}>
        <div className="grab" />
        {parsed?.transcript && <p className="quote">“{parsed.transcript}”</p>}
        {!parsed && <p className="warn-text">{s.voice.aiDown}</p>}
        <h2 className="h" style={{ fontSize: 21 }}>{s.voice.confirmTitle}</h2>
        {parsed?.warnings.includes('low_confidence') && <p className="warn-text">{s.voice.lowConfidence}</p>}
        {parsed?.warnings.includes('amount_missing') && <p className="warn-text">{s.voice.amountMissing}</p>}

        <div className="field">
          <span>{s.voice.type}</span>
          <select value={intent} onChange={(e) => setIntent(e.target.value as Intent)}>
            {(Object.keys(s.voice.intents) as Intent[]).map((k) => <option key={k} value={k}>{s.voice.intents[k]}</option>)}
          </select>
        </div>

        {needsCustomer && (
          <div className="field">
            <span>{s.voice.customer}</span>
            <div>
              <select value={customerId} onChange={(e) => setCustomerId(e.target.value)} aria-label={s.voice.customer}>
                <option value="" disabled>{s.voice.pickCustomer}</option>
                {customers.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                <option value={NEW}>+ {s.voice.newCustomer}</option>
              </select>
              {match?.status === 'matched' && customerId === match.customer_id && <span className="chip c-green">{s.voice.matched}</span>}
              {match?.status === 'ambiguous' && !customerId && <span className="chip c-saf">{s.voice.ambiguous}</span>}
            </div>
          </div>
        )}
        {needsCustomer && match?.status === 'ambiguous' && !customerId && (
          <div className="stack">
            <p className="sub">{s.voice.pickCustomer}</p>
            {match.candidates.map((c) => (
              <button key={c.customer_id} className="btn ghost small" onClick={() => setCustomerId(c.customer_id)}>{c.name}</button>
            ))}
            <button className="btn ghost small" onClick={() => setCustomerId(NEW)}>{s.voice.noneOfThese}</button>
          </div>
        )}
        {needsCustomer && customerId === NEW && (
          <NewCustomerForm
            initialName={draft?.customer_name ?? match?.name ?? ''}
            onCreated={(c) => {
              setCustomers((cs) => [...cs, c]);
              setCustomerId(c.id);
            }}
          />
        )}

        {intent === 'expense' && (
          <>
            <div className="field"><span>{s.voice.vendor}</span><input value={vendor} onChange={(e) => setVendor(e.target.value)} /></div>
            <div className="field">
              <span>{s.voice.category}</span>
              <select value={category} onChange={(e) => setCategory(e.target.value as ExpenseCategory)}>
                {(Object.keys(s.voice.categories) as ExpenseCategory[]).map((k) => <option key={k} value={k}>{s.voice.categories[k]}</option>)}
              </select>
            </div>
            <PaidChoice value={expStatus} onChange={setExpStatus} />
            {expStatus === 'unpaid' && (
              <div className="field"><span>{s.expense.dueDate}</span><input type="date" aria-label={s.expense.dueDate} value={due} onChange={(e) => setDue(e.target.value)} /></div>
            )}
          </>
        )}
        {intent === 'cash_sale' && <div className="field"><span>{s.voice.date}</span><span>{todayIST()}</span></div>}

        <div className="field">
          <span>{s.voice.amount}</span>
          <input inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} style={{ fontWeight: 700 }} />
        </div>
        {needsCustomer && (
          <div className="field"><span>{s.voice.items}</span><input value={items} onChange={(e) => setItems(e.target.value)} placeholder="doodh, atta" /></div>
        )}

        {selected && newTotal !== null && <p className="sub">{s.voice.newTotal(selected.name, formatPaise(newTotal))}</p>}
        {err && <p className="err" role="alert">{err}</p>}

        <div className="btns" style={{ marginTop: 6 }}>
          <button className="btn ghost" onClick={onClose}>{s.common.cancel}</button>
          <button className="btn" disabled={!canSave} onClick={save}>{busy ? '…' : s.common.save}</button>
        </div>
      </div>
    </div>
  );
}
