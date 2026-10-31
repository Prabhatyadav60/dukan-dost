"""Cash received at the counter, and today's sales broken down by who paid."""
from .. import clock
from ..db import MerchantScopedRepo
from ..errors import AppError
from ..money import format_paise
from . import cash, customers, ledger, thread


async def receive_cash(repo: MerchantScopedRepo, merchant: dict, amount: int, kind: str,
                       customer_id: str | None, note: str | None) -> dict:
    today = clock.today_ist()
    customer = None
    if kind == "udhaar":
        if not customer_id:
            raise AppError("validation_error", 422, "Customer chunein.", {"fields": [{"loc": ["customer_id"]}]})
        _, c = await ledger.add_entry(repo, customer_id, "payment", amount, [], "cash", note)
        customer = customers.public(await customers.to_api(repo, await customers.load(repo, customer_id)))
    receipt = await repo.insert("cash_receipts", {
        "kind": kind, "amount_paise": amount, "customer_id": customer_id,
        "customer_name": customer["name"] if customer else None, "note": (note or "").strip() or None,
        "date": today.isoformat(), "created_at": clock.now()})
    if kind == "sale":
        # once he starts entering cash sales, today's cash is what he entered (logged), not an estimate
        await repo.update("cash_logs", {"date": today.isoformat()},
                          {"$inc": {"amount_paise": amount}, "$set": {"source": "manual", "created_at": clock.now()}},
                          upsert=True)
    [day] = await cash.daily_sales(repo, merchant, today, today)
    if kind == "sale":
        await thread.add(repo, "assistant", "text",
                         f"{format_paise(amount)} cash bikri jod di. Aaj ka cash ab {format_paise(day['cash_paise'])}.",
                         {"type": "cash_log", "id": receipt["_id"]})
    return {"receipt": receipt_api(receipt), "today_cash_paise": day["cash_paise"], "customer": customer}


def receipt_api(r: dict) -> dict:
    return {"id": r["_id"], "kind": r["kind"], "amount_paise": r["amount_paise"], "customer_id": r.get("customer_id"),
            "customer_name": r.get("customer_name"), "note": r.get("note"), "created_at": clock.iso(r["created_at"])}


async def today(repo: MerchantScopedRepo, merchant: dict) -> dict:
    d = clock.today_ist()
    lo, hi = clock.ist_day_range(d)
    [day] = await cash.daily_sales(repo, merchant, d, d)
    txns = await repo.find("transactions", {"ts": {"$gte": lo, "$lt": hi}}, sort=[("ts", 1)])
    receipts = await repo.find("cash_receipts", {"date": d.isoformat(), "kind": "sale"}, sort=[("created_at", 1)])
    repaid = await repo.find("ledger_entries", {"type": "payment", "created_at": {"$gte": lo, "$lt": hi}},
                             sort=[("created_at", 1)])
    names = {c["_id"]: c["name"] for c in await repo.find("customers")}

    qr = [{"id": t["_id"], "ts": clock.iso(t["ts"]), "amount_paise": t["amount_paise"],
           "payer_name": t.get("payer_name") or "UPI customer", "payer_vpa": t.get("payer_vpa")} for t in txns]
    cash_items = [{"id": r["_id"], "ts": clock.iso(r["created_at"]), "amount_paise": r["amount_paise"],
                   "note": r.get("note"), "source": "manual"} for r in receipts]
    groups: dict[tuple, dict] = {}
    for q in qr:
        g = groups.setdefault(("qr", q["payer_vpa"] or q["payer_name"]),
                              {"name": q["payer_name"], "vpa": q["payer_vpa"], "channel": "qr", "count": 0,
                               "amount_paise": 0})
        g["count"] += 1
        g["amount_paise"] += q["amount_paise"]
    for c in cash_items:
        g = groups.setdefault(("cash", c["note"] or "Cash bikri"),
                              {"name": c["note"] or "Cash bikri", "vpa": None, "channel": "cash", "count": 0,
                               "amount_paise": 0})
        g["count"] += 1
        g["amount_paise"] += c["amount_paise"]
    itemised = sum(c["amount_paise"] for c in cash_items)
    return {
        "date": d.isoformat(), "total_paise": day["qr_paise"] + day["cash_paise"], "qr_paise": day["qr_paise"],
        "cash_paise": day["cash_paise"], "cash_source": day["cash_source"],
        "qr": qr, "cash": cash_items, "cash_unitemised_paise": max(0, day["cash_paise"] - itemised),
        "by_payer": sorted(groups.values(), key=lambda g: -g["amount_paise"]),
        "udhaar_repaid": [{"customer_id": e["customer_id"], "customer_name": names.get(e["customer_id"], "?"),
                           "amount_paise": e["amount_paise"], "source": e["source"], "ts": clock.iso(e["created_at"])}
                          for e in repaid],
    }
