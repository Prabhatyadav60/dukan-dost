const TZ = 'Asia/Kolkata';

/** Today's calendar date in IST as YYYY-MM-DD. */
export function todayIST(): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: TZ, year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
}

/** "2026-11-05" → "5 Nov" */
export function shortDate(ymd: string): string {
  const [y, m, d] = ymd.slice(0, 10).split('-').map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  return new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', timeZone: 'UTC' }).format(dt);
}

/** ISO timestamp → "12 Oct" in IST */
export function shortDateTime(iso: string): string {
  return new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', timeZone: TZ }).format(new Date(iso));
}

export function timeIST(iso: string): string {
  return new Intl.DateTimeFormat('en-IN', { hour: 'numeric', minute: '2-digit', timeZone: TZ }).format(new Date(iso));
}
