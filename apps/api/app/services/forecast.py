"""Deterministic forecast engine (spec §10). Pure functions: every rupee is computed here, never by a model."""
import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

FESTIVALS_PATH = Path(__file__).resolve().parents[2] / "data" / "festivals.json"
DUES_GRACE_DAYS = 3
CASH_HORIZON_DAYS = 30


def load_festivals() -> list[dict]:
    return json.loads(FESTIVALS_PATH.read_text())


def cash_estimate(qr_paise: int, cash_share: float) -> int:
    """Cash for a day with no log: qr × r / (1 − r)."""
    r = min(max(cash_share, 0.0), 0.89)
    return round(qr_paise * r / (1 - r)) if r > 0 else 0


def calibrate_cash_share(purchases_paise: int, digital_paise: int, margin: float) -> float:
    """Monthly calibration: implied cash = purchases ÷ (1 − margin) − digital. Returns the new r."""
    total = purchases_paise / (1 - margin)
    cash = max(0.0, total - digital_paise)
    return round(cash / total, 4) if total > 0 else 0.0


@dataclass
class Bill:
    amount_paise: int
    due: date | None  # None = no due date printed
    vendor: str = "Bill"
    id: str | None = None


@dataclass
class ForecastInputs:
    today: date
    horizon: int  # days shown in the sales chart; the cash projection always looks CASH_HORIZON_DAYS ahead
    daily_totals: dict[date, int]  # past days: QR + cash (logged or estimated)
    festivals: list[dict]
    cash_on_hand_paise: int
    received_paise: int  # ledger payments since cash_on_hand_at
    unpaid_bills: list[Bill] = field(default_factory=list)
    collectible_paise: int = 0
    margin: float = 0.10
    spent_paise: int = 0  # bills/expenses paid since cash_on_hand was counted


def _short(d: date) -> str:
    return d.strftime("%-d %b")


def compute(inp: ForecastInputs) -> dict:
    """Day-by-day cash projection. Each day: unpaid bills due that day leave first (distributors collect
    in the morning), then the day's profit on normal sales and the full revenue of extra festival sales
    (that stock was paid for in advance) come in; Diwali stock is bought on the evening of buy_by.
    The lowest balance is the real shortfall; udhaar collection covers what it can, a loan the rest."""
    # baseline per weekday from the last 28 completed days
    by_wd: dict[int, list[int]] = {}
    for i in range(1, 29):
        d = inp.today - timedelta(days=i)
        if d in inp.daily_totals:
            by_wd.setdefault(d.weekday(), []).append(inp.daily_totals[d])
    overall = [v for vs in by_wd.values() for v in vs]
    fallback = round(sum(overall) / len(overall)) if overall else 0
    baseline = {wd: round(sum(vs) / len(vs)) for wd, vs in by_wd.items()}

    horizon_end = inp.today + timedelta(days=inp.horizon)
    festival = None
    for f in inp.festivals:
        start = date.fromisoformat(f["window"][0])
        if inp.today < start <= horizon_end:
            festival = f
            break
    uplift = {date.fromisoformat(k): v for k, v in (festival or {}).get("uplift", {}).items()}

    def day(d: date) -> dict:
        b = baseline.get(d.weekday(), fallback)
        u = uplift.get(d, 1.0)
        return {"date": d, "baseline_paise": b, "uplift": u, "forecast_paise": round(b * u)}

    days = [day(inp.today + timedelta(days=i)) for i in range(1, CASH_HORIZON_DAYS + 1)]
    daily = days[: inp.horizon]

    buy_by = stock_needed = None
    if festival:
        w0, w1 = (date.fromisoformat(x) for x in festival["window"])
        buy_by = w0 - timedelta(days=1)
        extra = sum(x["forecast_paise"] - x["baseline_paise"] for x in days if w0 <= x["date"] <= w1)
        stock_needed = round(extra * (1 - inp.margin))

    first_day = inp.today + timedelta(days=1)
    last_day = inp.today + timedelta(days=CASH_HORIZON_DAYS)
    outflows: dict[date, list[dict]] = {}
    for b in inp.unpaid_bills:
        if b.due is not None and b.due > last_day:
            continue
        when = b.due if b.due is not None and b.due >= first_day else first_day  # overdue/undated: pay now
        kind = "bill" if b.due is not None and b.due >= first_day else "overdue_bills"
        label = b.vendor if kind == "bill" else f"{b.vendor} (overdue)" if b.due else f"{b.vendor} (no due date)"
        outflows.setdefault(when, []).append({"kind": kind, "label": label, "amount_paise": -b.amount_paise})

    start_balance = inp.cash_on_hand_paise + inp.received_paise - inp.spent_paise
    balance = start_balance
    low = (inp.today, start_balance)
    first_negative: date | None = None
    timeline: list[dict] = []
    profit_to_buy = 0
    cash_before_stock = start_balance
    w0 = date.fromisoformat(festival["window"][0]) if festival else None
    w1 = date.fromisoformat(festival["window"][1]) if festival else None
    for x in days:
        d = x["date"]
        events = list(outflows.get(d, []))
        balance += sum(e["amount_paise"] for e in events)
        shown = balance
        if balance < low[1]:
            low = (d, balance)
        if balance < 0 and first_negative is None:
            first_negative = d
        profit = round(x["baseline_paise"] * inp.margin)
        extra_rev = x["forecast_paise"] - x["baseline_paise"] if festival and w0 <= d <= w1 else 0
        if extra_rev:
            events.append({"kind": "festival_sales", "label": f"{festival['name']} ki extra bikri",
                           "amount_paise": extra_rev})
        balance += profit + extra_rev
        if extra_rev:
            shown = balance
        if buy_by and d <= buy_by:
            profit_to_buy += round(x["forecast_paise"] * inp.margin)
        if buy_by and d == buy_by:
            cash_before_stock = balance
            events.append({"kind": "stock", "label": f"{festival['name']} ka maal", "amount_paise": -stock_needed})
            balance -= stock_needed
            shown = balance
            if balance < low[1]:
                low = (d, balance)
            if balance < 0 and first_negative is None:
                first_negative = d
        if events:
            timeline.append({"date": d, "balance_paise": shown, "events": events})

    gap = max(0, -low[1])
    by_date = None
    if gap:
        by_date = first_negative
        # a shortfall right after the stock purchase must be arranged before buying the stock
        if buy_by and first_negative and first_negative <= buy_by + timedelta(days=DUES_GRACE_DAYS):
            by_date = buy_by
    # what causes the shortfall: buying festival stock, or a bill on the low-point day
    # the "why" comes from the deepest point; by_date is when money first runs short
    reason = None
    if gap:
        if buy_by and low[0] <= buy_by + timedelta(days=DUES_GRACE_DAYS):
            reason = {"kind": "stock", "label": f"{festival['name']} ka maal", "amount_paise": stock_needed}
        else:
            day_bills = [e for e in outflows.get(low[0], [])]
            if day_bills:
                big = min(day_bills, key=lambda e: e["amount_paise"])
                reason = {"kind": "bills", "label": big["label"], "amount_paise": -big["amount_paise"]}
    collect = min(gap, inp.collectible_paise)
    dues = -sum(e["amount_paise"] for es in outflows.values() for e in es)
    counted = {b.id for b in inp.unpaid_bills if b.due is None or b.due <= last_day}
    breakdown = {"cash_on_hand_paise": inp.cash_on_hand_paise, "received_paise": inp.received_paise,
                 "profit_to_buy_paise": profit_to_buy, "dues_paise": dues, "spent_paise": inp.spent_paise}
    return {
        "breakdown": breakdown,
        "festival": {"name": festival["name"], "date": festival["date"], "window": festival["window"]} if festival else None,
        "buy_by_date": buy_by, "daily": daily, "stock_needed_paise": stock_needed or 0,
        # money free for festival stock: if the shortfall hits around the purchase, it is what is left after
        # those bills; if it comes later from other bills, the stock itself is covered by cash in hand by buy_by
        "cash_available_paise": (max(0, stock_needed - gap) if reason and reason["kind"] == "stock" else cash_before_stock)
        if festival else max(0, low[1]),
        "shortfall_reason": reason,
        "cash_before_stock_paise": cash_before_stock if festival else None,
        "gap_paise": gap, "dues_paise": dues, "profit_to_buy_paise": profit_to_buy,
        "shortfall_date": by_date, "low_point": {"date": low[0], "balance_paise": low[1]},
        "timeline": timeline, "counted_bill_ids": counted,
        "plan": {"collect_paise": collect, "loan_paise": gap - collect},
        "assumptions": {"margin": inp.margin, "cash_horizon_days": CASH_HORIZON_DAYS},
    }
