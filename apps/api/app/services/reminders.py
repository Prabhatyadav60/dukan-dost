from .. import clock
from ..db import MerchantScopedRepo
from ..errors import not_found
from ..money import format_paise
from . import customers, events, payments, writers


async def plan(repo: MerchantScopedRepo, merchant: dict) -> list[dict]:
    out = []
    for c in await repo.find("customers"):
        if c["balance_paise"] <= 0:
            continue
        info = await customers.to_api(repo, c)
        base = {"reminder_id": None, "customer": {"id": c["_id"], "name": c["name"]},
                "amount_paise": c["balance_paise"], "attempt": info["reminder"]["attempts_on_current_debt"] + 1,
                "message": None, "payment_link": None, "wa_url": None,
                "skipped_reason": info["_skipped_reason"], "reason": info["reminder"]["reason"],
                "late_payer": info["late_payer"]}
        if not info["reminder"]["eligible"]:
            base["attempt"] = min(base["attempt"], 2)
            out.append(base)
            continue
        f = customers.fifo(await repo.find("ledger_entries", {"customer_id": c["_id"]}))
        items = sorted({i for o in f["open"] for i in o["entry"].get("items", [])})
        amount = format_paise(c["balance_paise"])
        link = await payments.create_link(repo, c["_id"], c["balance_paise"])
        url = payments.provider.link_url(link["_id"])
        template = await writers.reminder(c["name"], merchant["shop_name"], amount, items, base["attempt"])
        message = template.replace("{link}", url)
        drafted = await repo.find_one("reminders", {"customer_id": c["_id"], "status": "drafted"})
        fields = {"amount_paise": c["balance_paise"], "attempt": base["attempt"], "message": message,
                  "payment_link_id": link["_id"]}
        if drafted:
            await repo.update("reminders", {"_id": drafted["_id"]}, {"$set": fields})
            rid = drafted["_id"]
        else:
            rid = (await repo.insert("reminders", {**fields, "customer_id": c["_id"], "status": "drafted",
                                                   "created_at": clock.now(), "sent_at": None}))["_id"]
            await events.log(repo, "reminder_drafted", rid)
        out.append({**base, "reminder_id": rid, "message": message, "payment_link": payments.link_api(link),
                    "wa_url": payments.wa_url(c["phone_e164"], message)})
    order = {None: 0}
    return sorted(out, key=lambda r: (order.get(r["skipped_reason"], 1), -r["amount_paise"]))


async def mark_sent(repo: MerchantScopedRepo, reminder_id: str) -> dict:
    r = await repo.get("reminders", reminder_id)
    if not r:
        raise not_found()
    if r["status"] == "drafted":
        now = clock.now()
        await repo.update("reminders", {"_id": reminder_id}, {"$set": {"status": "sent", "sent_at": now}})
        await events.log(repo, "reminder_sent", reminder_id)
        r.update(status="sent", sent_at=now)
    return {"reminder_id": reminder_id, "status": r["status"], "sent_at": clock.iso(r.get("sent_at"))}
