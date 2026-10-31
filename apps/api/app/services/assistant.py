"""Shop Q&A: everything the munshi may talk about, as formatted facts. The model only phrases them."""
import asyncio
from datetime import timedelta

from .. import clock
from ..ai import get_llm
from ..config import get_settings
from ..db import MerchantScopedRepo
from ..money import format_paise
from . import cash, customers, forecast, thread


def _day(d: str | None) -> str | None:
    from datetime import date
    return date.fromisoformat(d).strftime("%-d %b") if d else None


async def shop_context(repo: MerchantScopedRepo, merchant: dict) -> dict:
    today = clock.today_ist()
    week, custs, unpaid, paid, entries, scan, inputs = await asyncio.gather(
        cash.daily_sales(repo, merchant, today - timedelta(days=6), today),
        customers.list_api(repo),
        repo.find("expenses", {"status": "unpaid"}, sort=[("due_date", 1)]),
        repo.find("expenses", {"status": "paid"}, sort=[("paid_at", -1)], limit=10),
        repo.find("ledger_entries", sort=[("created_at", -1)], limit=15),
        repo.find_one("shelf_scans", sort=[("created_at", -1)]),
        cash.forecast_inputs(repo, merchant, 14, get_settings().forecast_margin))
    names = {c["id"]: c["name"] for c in custs}
    t = week[-1]
    f = forecast.compute(inputs)
    return {
        "shop_name": merchant["shop_name"], "owner_name": merchant["owner_name"], "today_date": today.isoformat(),
        "today": {"qr": format_paise(t["qr_paise"]), "cash": format_paise(t["cash_paise"]),
                  "cash_is": "owner told us" if t["cash_source"] == "logged" else "estimate",
                  "total": format_paise(t["qr_paise"] + t["cash_paise"])},
        "last_7_days": [{"date": d["date"].isoformat(), "total": format_paise(d["qr_paise"] + d["cash_paise"])}
                        for d in week],
        "last_7_days_total": format_paise(sum(d["qr_paise"] + d["cash_paise"] for d in week)),
        "udhaar_total": format_paise(sum(c["balance_paise"] for c in custs)),
        "customers": [{"name": c["name"], "balance": format_paise(c["balance_paise"]),
                       "owing_since": c["oldest_unpaid_at"][:10] if c["oldest_unpaid_at"] else None,
                       "last_paid": c["last_payment_at"][:10] if c["last_payment_at"] else None,
                       "usually_pays_late": c["late_payer"], "reminder": c["reminder"]["reason"]}
                      for c in custs],
        "unpaid_bills": [{"vendor": e["vendor"], "amount": format_paise(e["total_paise"]),
                          "due_date": _day(e.get("due_date"))} for e in unpaid],
        "recently_paid_bills": [{"vendor": e["vendor"], "amount": format_paise(e["total_paise"])} for e in paid],
        "recent_ledger": [{"customer": names.get(e["customer_id"], "?"), "type": e["type"],
                           "amount": format_paise(e["amount_paise"]), "items": e.get("items", []),
                           "date": clock.to_ist_date(e["created_at"]).isoformat()} for e in entries],
        "forecast": None if not (f["festival"] or f["gap_paise"]) else {
            "festival": f["festival"]["name"] if f["festival"] else None,
            "festival_date": _day(f["festival"]["date"]) if f["festival"] else None,
            "buy_stock_by": f["buy_by_date"].strftime("%-d %b") if f["buy_by_date"] else None,
            "money_needed_by": f["shortfall_date"].strftime("%-d %b") if f["shortfall_date"] else None,
            "lowest_cash_next_30_days": format_paise(f["low_point"]["balance_paise"]),
            "stock_needed": format_paise(f["stock_needed_paise"]),
            "cash_available": format_paise(f["cash_available_paise"]), "shortfall": format_paise(f["gap_paise"]),
            "collect_udhaar": format_paise(f["plan"]["collect_paise"]),
            "loan_offer": format_paise(f["plan"]["loan_paise"])},
        "latest_shelf_scan": None if not scan else {
            "date": clock.to_ist_date(scan["created_at"]).isoformat(), "findings": scan["findings"]},
    }


async def answer(repo: MerchantScopedRepo, merchant: dict, question: str) -> str:
    context, recent = await asyncio.gather(shop_context(repo, merchant),
                                           repo.find("thread_messages", sort=[("created_at", -1)], limit=11))
    # the question itself was just added to the thread; history is what came before it
    history = [{"from": m["role"], "text": m["text"]} for m in reversed(recent[1:]) if m.get("text")]
    try:
        text = await get_llm().ask(question, context, history)
    except Exception:  # noqa: BLE001 — never leave the merchant without a reply
        text = "Maaf kijiye, abhi jawab nahi de paa raha. Thodi der baad poochhiye."
    await thread.add(repo, "assistant", "text", text.strip())
    return text.strip()
