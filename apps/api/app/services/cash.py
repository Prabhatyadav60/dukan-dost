"""Daily sales (QR + cash, logged or estimated) and forecast input loading."""
from datetime import date, timedelta

from .. import clock
from ..db import MerchantScopedRepo
from . import forecast


async def daily_sales(repo: MerchantScopedRepo, merchant: dict, start: date, end: date) -> list[dict]:
    """Inclusive IST date range → [{date, qr_paise, cash_paise, cash_source}]."""
    lo, _ = clock.ist_day_range(start)
    _, hi = clock.ist_day_range(end)
    qr: dict[date, int] = {}
    for t in await repo.find("transactions", {"ts": {"$gte": lo, "$lt": hi}}):
        d = clock.to_ist_date(t["ts"])
        qr[d] = qr.get(d, 0) + t["amount_paise"]
    logs = {c["date"]: c["amount_paise"] for c in await repo.find(
        "cash_logs", {"date": {"$gte": start.isoformat(), "$lte": end.isoformat()}})}
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
    days = await daily_sales(repo, merchant, today - timedelta(days=28), today - timedelta(days=1))
    since = merchant.get("cash_on_hand_at") or clock.ist_midnight_utc(today)
    received = sum(e["amount_paise"] for e in await repo.find(
        "ledger_entries", {"type": "payment", "created_at": {"$gte": since}}))
    unpaid = [(date.fromisoformat(e["due_date"]) if e.get("due_date") else None, e["total_paise"])
              for e in await repo.find("expenses", {"status": "unpaid"})]
    collectible = sum(c["balance_paise"] for c in await repo.find("customers")
                      if c["balance_paise"] > 0 and c.get("phone_e164") and not c.get("do_not_remind"))
    return forecast.ForecastInputs(
        today=today, horizon=horizon,
        daily_totals={x["date"]: x["qr_paise"] + x["cash_paise"] for x in days},
        festivals=forecast.load_festivals(), cash_on_hand_paise=merchant.get("cash_on_hand_paise", 0),
        received_paise=received, unpaid_expenses=unpaid, collectible_paise=collectible, margin=margin)
