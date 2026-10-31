"""Daily sales (QR + cash, logged or estimated) and forecast input loading."""
import asyncio
from datetime import date, timedelta

from .. import clock
from ..db import MerchantScopedRepo
from . import forecast


async def daily_sales(repo: MerchantScopedRepo, merchant: dict, start: date, end: date) -> list[dict]:
    """Inclusive IST date range → [{date, qr_paise, cash_paise, cash_source}]."""
    lo, _ = clock.ist_day_range(start)
    _, hi = clock.ist_day_range(end)
    txns, cash_logs = await asyncio.gather(
        repo.find("transactions", {"ts": {"$gte": lo, "$lt": hi}}),
        repo.find("cash_logs", {"date": {"$gte": start.isoformat(), "$lte": end.isoformat()}}))
    qr: dict[date, int] = {}
    for t in txns:
        d = clock.to_ist_date(t["ts"])
        qr[d] = qr.get(d, 0) + t["amount_paise"]
    logs = {c["date"]: c["amount_paise"] for c in cash_logs}
    r = merchant.get("cash_share_estimate", 0.3)
    out = []
    d = start
    while d <= end:
        q = qr.get(d, 0)
        if d.isoformat() in logs:
            out.append({"date": d, "qr_paise": q, "cash_paise": logs[d.isoformat()], "cash_source": "logged"})
        else:
            out.append({"date": d, "qr_paise": q, "cash_paise": forecast.cash_estimate(q, r),
                        "cash_source": "estimated"})
        d += timedelta(days=1)
    return out


async def forecast_inputs(repo: MerchantScopedRepo, merchant: dict, horizon: int, margin: float):
    today = clock.today_ist()
    since = merchant.get("cash_on_hand_at") or clock.ist_midnight_utc(today)
    days, payments, expenses, paid, custs = await asyncio.gather(
        daily_sales(repo, merchant, today - timedelta(days=28), today - timedelta(days=1)),
        repo.find("ledger_entries", {"type": "payment", "created_at": {"$gte": since}}),
        repo.find("expenses", {"status": "unpaid"}),
        repo.find("expenses", {"status": "paid", "paid_at": {"$gte": since}}),
        repo.find("customers"))
    received = sum(e["amount_paise"] for e in payments)
    unpaid = [forecast.Bill(amount_paise=e["total_paise"], vendor=e["vendor"], id=e["_id"],
                            due=date.fromisoformat(e["due_date"]) if e.get("due_date") else None) for e in expenses]
    collectible = sum(c["balance_paise"] for c in custs
                      if c["balance_paise"] > 0 and c.get("phone_e164") and not c.get("do_not_remind"))
    return forecast.ForecastInputs(
        today=today, horizon=horizon,
        daily_totals={x["date"]: x["qr_paise"] + x["cash_paise"] for x in days},
        festivals=forecast.load_festivals(), cash_on_hand_paise=merchant.get("cash_on_hand_paise", 0),
        received_paise=received, unpaid_bills=unpaid, collectible_paise=collectible, margin=margin,
        spent_paise=sum(e["total_paise"] for e in paid))
