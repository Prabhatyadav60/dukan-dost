// Shapes mirror the API contract (spec §7). Money is always integer paise.

export interface Merchant {
  id: string;
  shop_name: string;
  owner_name: string;
  phone: string;
  consent_given: boolean;
  cash_share_estimate: number;
  cash_on_hand_paise: number;
}

export interface SessionResponse {
  access_token: string;
  token_type: 'bearer';
  expires_at: string;
  merchant: Merchant;
}

export type CashSource = 'logged' | 'estimated';

export interface HomeSummary {
  date: string;
  sales: { qr_paise: number; cash_paise: number; cash_source: CashSource; total_paise: number };
  udhaar_total_paise: number;
  customers_with_balance: number;
  restock_sections: number | null;
  bills_due: { expense_id: string; vendor: string; total_paise: number; due_date: string }[];
  alert: { type: 'cash_gap'; gap_paise: number; by_date: string; message: string } | null;
}

export interface ThreadMessage {
  id: string;
  role: 'merchant' | 'assistant';
  kind: 'voice' | 'photo' | 'text' | 'alert';
  text: string;
  ref: { type: 'ledger_entry' | 'expense' | 'forecast' | 'cash_log'; id: string } | null;
  created_at: string;
}

export type Intent = 'credit' | 'payment' | 'expense' | 'cash_sale';
export type ExpenseCategory = 'stock' | 'rent' | 'staff' | 'other';

export interface EntryDraft {
  intent: Intent;
  customer_name: string | null;
  amount_paise: number;
  items: string[];
  vendor: string | null;
  category: ExpenseCategory | null;
  confidence: number;
}

export interface CustomerCandidate {
  customer_id: string;
  name: string;
  score: number;
}

export interface VoiceParseResponse {
  transcript: string;
  draft: EntryDraft;
  customer_match: {
    status: 'matched' | 'ambiguous' | 'new' | 'not_applicable';
    customer_id: string | null;
    name: string | null;
    candidates: CustomerCandidate[];
  };
  warnings: ('low_confidence' | 'amount_missing' | 'customer_unknown')[];
}

export interface Customer {
  id: string;
  name: string;
  phone_e164: string | null;
  aliases: string[];
  balance_paise: number;
  oldest_unpaid_at: string | null;
  last_payment_at: string | null;
  late_payer: boolean;
  do_not_remind: boolean;
  reminder: { eligible: boolean; reason: string; attempts_on_current_debt: number };
}

export type EntrySource = 'voice' | 'text' | 'manual' | 'pay_link';

export interface LedgerEntry {
  id: string;
  customer_id: string;
  type: 'credit' | 'payment';
  amount_paise: number;
  items: string[];
  source: EntrySource;
  transcript: string | null;
  created_at: string;
}

export interface LineItem {
  name: string;
  qty: number | null;
  unit: string | null;
  amount_paise: number;
}

export interface BillScanResponse {
  draft: {
    vendor: string | null;
    bill_date: string | null;
    due_date: string | null;
    line_items: LineItem[];
    total_paise: number;
    unreadable_fields: string[];
  };
  checks: { sum_matches: boolean; line_items_sum_paise: number; difference_paise: number };
  image_keys: string[];
}

export interface Expense {
  id: string;
  vendor: string;
  line_items: LineItem[];
  total_paise: number;
  due_date: string | null;
  category: ExpenseCategory;
  status: 'unpaid' | 'paid';
  source: 'bill_scan' | 'voice' | 'text' | 'manual';
  image_keys: string[];
  created_at: string;
  paid_at: string | null;
}

export interface CashLog {
  id?: string;
  date: string;
  amount_paise: number;
  source: 'voice' | 'text' | 'manual';
}

export interface Forecast {
  forecast_id: string;
  generated_at: string;
  horizon_days: number;
  festival: { name: string; date: string; window: [string, string] } | null;
  buy_by_date: string | null;
  daily: { date: string; baseline_paise: number; uplift: number; forecast_paise: number }[];
  stock_needed_paise: number;
  cash_available_paise: number;
  gap_paise: number;
  plan: { collect_paise: number; loan_paise: number };
  explanation: string;
  assumptions: { margin: number; cash_share: number; dues_grace_days: number };
}

export interface LoanOffer {
  offer_id: string;
  amount_paise: number;
  reason: string;
  forecast_id: string;
  status: 'shown' | 'interested';
  disclaimer: string;
}

export type SkippedReason = 'no_phone' | 'do_not_remind' | 'too_recent' | 'max_attempts' | 'no_balance';

export interface ReminderDraft {
  reminder_id: string | null;
  customer: { id: string; name: string };
  amount_paise: number;
  attempt: number;
  message: string;
  payment_link: { id: string; url: string; expires_at: string } | null;
  wa_url: string | null;
  skipped_reason: SkippedReason | null;
}

export interface PublicPay {
  shop_name: string;
  customer_name: string;
  amount_paise: number;
  items: { date: string; items: string[]; amount_paise: number }[];
  status: 'created' | 'paid' | 'expired';
  expires_at: string;
}
