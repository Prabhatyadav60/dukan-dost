const whole = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 });
const frac = new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** ₹1,250 — no decimals unless paise are non-zero. */
export function formatPaise(paise: number): string {
  const sign = paise < 0 ? '−' : '';
  const abs = Math.abs(paise);
  const body = abs % 100 === 0 ? whole.format(abs / 100) : frac.format(abs / 100);
  return `${sign}₹${body}`;
}

/** "450" or "1,250.50" typed by the user → paise; null if unparsable. */
export function rupeesToPaise(input: string): number | null {
  const n = Number(input.replace(/[₹,\s]/g, ''));
  if (!Number.isFinite(n) || n <= 0) return null;
  return Math.round(n * 100);
}

export function paiseToRupeesInput(paise: number): string {
  return paise % 100 === 0 ? String(paise / 100) : (paise / 100).toFixed(2);
}
