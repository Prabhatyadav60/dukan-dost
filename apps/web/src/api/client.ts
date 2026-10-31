import type {
  BillScanResponse, CashLog, Customer, EntryDraft, Expense, ExpenseCategory, Forecast, HomeSummary,
  LedgerEntry, LineItem, LoanOffer, Merchant, PublicPay, ReminderDraft, SessionResponse, ThreadMessage,
  VoiceParseResponse,
} from './types';

export const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(/\/$/, '');

const TOKEN_KEY = 'dd_token';
let token: string | null = sessionStorage.getItem(TOKEN_KEY);

export function getToken(): string | null {
  return token;
}
export function setToken(t: string | null): void {
  token = t;
  if (t) sessionStorage.setItem(TOKEN_KEY, t);
  else sessionStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public details: unknown = {}) {
    super(message);
  }
}

type Opts = { method?: string; body?: unknown; form?: FormData; idempotencyKey?: string; auth?: boolean };

async function request<T>(path: string, opts: Opts = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (opts.auth !== false && token) headers.Authorization = `Bearer ${token}`;
  if (opts.idempotencyKey) headers['Idempotency-Key'] = opts.idempotencyKey;
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(opts.body);
  }
  let res: Response;
  try {
    res = await fetch(API_BASE + path, { method: opts.method ?? (body ? 'POST' : 'GET'), headers, body });
  } catch {
    throw new ApiError(0, 'network', 'Network nahi mila. Internet check karein.');
  }
  if (res.status === 204) return null as T;
  const text = await res.text();
  const json: unknown = text ? safeJson(text) : null;
  if (!res.ok) {
    const err = (json as { error?: { code?: string; message?: string; details?: unknown } } | null)?.error;
    if (res.status === 401 && err?.code === 'unauthenticated') {
      setToken(null);
      if (!location.pathname.startsWith('/login') && !location.pathname.startsWith('/pay/')) location.assign('/login');
    }
    throw new ApiError(res.status, err?.code ?? 'http_' + res.status, err?.message ?? res.statusText, err?.details);
  }
  return json as T;
}

function safeJson(t: string): unknown {
  try {
    return JSON.parse(t);
  } catch {
    return null;
  }
}

export const api = {
  login: (phone: string, otp: string) =>
    request<SessionResponse>('/v1/auth/session', { body: { phone, otp }, auth: false }),
  me: () => request<Merchant>('/v1/me'),
  consent: (b: { data_use: boolean; cash_share_estimate: number; cash_on_hand_paise: number }) =>
    request<Merchant>('/v1/onboarding/consent', { body: b }),

  home: () => request<HomeSummary>('/v1/home/summary'),
  thread: (limit = 50) => request<{ messages: ThreadMessage[] }>(`/v1/thread?limit=${limit}`),

  voiceParseAudio: (blob: Blob, filename: string) => {
    const f = new FormData();
    f.append('audio', blob, filename);
    return request<VoiceParseResponse>('/v1/voice/parse', { form: f });
  },
  voiceParseText: (text: string) => {
    const f = new FormData();
    f.append('text', text);
    return request<VoiceParseResponse>('/v1/voice/parse', { form: f });
  },

  customers: () => request<{ customers: Customer[] }>('/v1/customers'),
  createCustomer: (b: { name: string; phone_e164: string | null; aliases: string[] }) =>
    request<Customer>('/v1/customers', { body: b }),
  patchCustomer: (id: string, b: { phone_e164?: string | null; aliases?: string[]; do_not_remind?: boolean }) =>
    request<Customer>(`/v1/customers/${id}`, { method: 'PATCH', body: b }),
  customerEntries: (id: string) => request<{ entries: LedgerEntry[] }>(`/v1/customers/${id}/entries`),
  createEntry: (
    b: { customer_id: string; type: 'credit' | 'payment'; amount_paise: number; items: string[];
      source: 'voice' | 'text' | 'manual'; transcript: string | null },
    key: string,
  ) => request<{ entry: LedgerEntry; customer: Customer }>('/v1/ledger/entries', { body: b, idempotencyKey: key }),

  scanBill: (images: Blob[]) => {
    const f = new FormData();
    images.forEach((b, i) => f.append('images', b, `page-${i + 1}.jpg`));
    return request<BillScanResponse>('/v1/bills/scan', { form: f });
  },
  createExpense: (
    b: { vendor: string; line_items: LineItem[]; total_paise: number; due_date: string | null;
      category: ExpenseCategory; source: Expense['source']; image_keys: string[] },
    key: string,
  ) => request<Expense>('/v1/expenses', { body: b, idempotencyKey: key }),

  cashLog: (b: CashLog, key: string) => request<CashLog>('/v1/cash/logs', { body: b, idempotencyKey: key }),

  forecast: (horizon = 14) => request<Forecast>(`/v1/forecast?horizon=${horizon}`),
  loanOffer: () => request<LoanOffer | null>('/v1/loan-offer'),
  loanInterest: (id: string) => request<LoanOffer>(`/v1/loan-offer/${id}/interest`, { method: 'POST' }),

  planReminders: () => request<{ reminders: ReminderDraft[] }>('/v1/reminders/plan', { method: 'POST' }),
  reminderSent: (id: string) => request<{ reminder_id: string; status: 'sent'; sent_at: string }>(
    `/v1/reminders/${id}/sent`, { method: 'POST' }),

  publicPay: (linkId: string) => request<PublicPay>(`/public/pay/${linkId}`, { auth: false }),
  publicPayNow: (linkId: string) =>
    request<{ status: 'paid'; paid_at: string }>(`/public/pay/${linkId}/pay`, { method: 'POST', auth: false }),
};

export type { EntryDraft };
