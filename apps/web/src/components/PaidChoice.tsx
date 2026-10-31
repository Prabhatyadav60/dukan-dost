import type { ExpenseStatus } from '../api/types';
import { s } from '../strings';

/** Required "paid already / pay later" choice for an expense — it changes the cash forecast. */
export function PaidChoice({ value, onChange }: { value: ExpenseStatus | null; onChange: (v: ExpenseStatus) => void }) {
  return (
    <div className="stack" style={{ gap: 6 }}>
      <p className="sub">{s.expense.question}</p>
      <div className="seg" role="radiogroup" aria-label={s.expense.question}>
        {(['paid', 'unpaid'] as const).map((v) => (
          <button key={v} type="button" role="radio" aria-checked={value === v} className={value === v ? 'on' : ''}
            onClick={() => onChange(v)}>
            {v === 'paid' ? s.expense.paid : s.expense.unpaid}
          </button>
        ))}
      </div>
    </div>
  );
}
