"""Customers, FIFO settlement maths, late-payer flag and reminder eligibility (spec §11)."""
import asyncio
import re
from datetime import datetime, timedelta

from rapidfuzz import fuzz

from .. import clock
from ..db import MerchantScopedRepo
from ..errors import AppError, not_found

LATE_PAYER_DAYS = 21
REMIND_AFTER_DAYS = 14
REMIND_GAP_DAYS = 3
MAX_REMINDERS = 2


def name_key(name: str) -> str:
    s = re.sub(r"\bji\b", " ", name.casefold())
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s)).strip()


def fifo(entries: list[dict]) -> dict:
    """Payments settle the oldest credits first. Returns open credits and settlement durations."""
    open_credits: list[dict] = []
    settle_days: list[float] = []
    last_payment_at: datetime | None = None
    for e in sorted(entries, key=lambda e: e["created_at"]):
        if e["type"] == "credit":
            open_credits.append({"entry": e, "remaining": e["amount_paise"]})
        else:
            last_payment_at = e["created_at"]
            left = e["amount_paise"]
            while left > 0 and open_credits:
                c = open_credits[0]
                take = min(left, c["remaining"])
                c["remaining"] -= take
                left -= take
                if c["remaining"] == 0:
                    settle_days.append((e["created_at"] - c["entry"]["created_at"]).total_seconds() / 86400)
                    open_credits.pop(0)
    return {"open": open_credits, "settle_days": settle_days, "last_payment_at": last_payment_at}


def reminder_status(c: dict, f: dict, reminders: list[dict], now: datetime) -> dict:
    """Spec §11: eligibility plus a human chip label in `reason`."""
    sent = [r for r in reminders if r.get("status") in ("sent", "paid") and r.get("sent_at")
            and (f["last_payment_at"] is None or r["sent_at"] > f["last_payment_at"])]
    attempts = len(sent)
    oldest = f["open"][0]["entry"]["created_at"] if f["open"] else None

    def out(eligible: bool, skipped: str | None, reason: str) -> dict:
        return {"eligible": eligible, "skipped_reason": skipped, "reason": reason, "attempts_on_current_debt": attempts}

    if c["balance_paise"] <= 0:
        return out(False, "no_balance", "Koi baaki nahi")
    if c.get("do_not_remind"):
        return out(False, "do_not_remind", "Reminder band hai")
    if not c.get("phone_e164"):
        return out(False, "no_phone", "Phone number nahi hai")
    age = (now - oldest).days if oldest else 0
    if age < REMIND_AFTER_DAYS:
        return out(False, "too_recent", f"{age} din purana · abhi nahi")
    if attempts >= MAX_REMINDERS:
        return out(False, "max_attempts", "2 reminder ho chuke")
    if sent and (now - max(r["sent_at"] for r in sent)) < timedelta(days=REMIND_GAP_DAYS):
        return out(False, "too_recent", "Reminder abhi bheja tha")
    return out(True, None, "Reminder ready")


async def load(repo: MerchantScopedRepo, customer_id: str) -> dict:
    c = await repo.get("customers", customer_id)
    if not c:
        raise not_found()
    return c


async def to_api(repo: MerchantScopedRepo, c: dict, entries: list[dict] | None = None,
                 reminders: list[dict] | None = None) -> dict:
    if entries is None or reminders is None:
        entries, reminders = await asyncio.gather(repo.find("ledger_entries", {"customer_id": c["_id"]}),
                                                  repo.find("reminders", {"customer_id": c["_id"]}))
    f = fifo(entries)
    late = len(f["settle_days"]) >= 2 and sum(f["settle_days"]) / len(f["settle_days"]) > LATE_PAYER_DAYS
    rs = reminder_status(c, f, reminders, clock.now())
    return {
        "id": c["_id"], "name": c["name"], "phone_e164": c.get("phone_e164"), "aliases": c.get("aliases", []),
        "balance_paise": c["balance_paise"],
        "oldest_unpaid_at": clock.iso(f["open"][0]["entry"]["created_at"]) if f["open"] else None,
        "last_payment_at": clock.iso(f["last_payment_at"]),
        "late_payer": late, "do_not_remind": bool(c.get("do_not_remind")),
        "reminder": {k: rs[k] for k in ("eligible", "reason", "attempts_on_current_debt")},
        "_skipped_reason": rs["skipped_reason"],
    }


def public(c: dict) -> dict:
    return {k: v for k, v in c.items() if not k.startswith("_")}


async def list_api(repo: MerchantScopedRepo) -> list[dict]:
    # three queries total instead of two per customer (each is a network round trip to Atlas)
    custs, entries, reminders = await asyncio.gather(repo.find("customers"), repo.find("ledger_entries"),
                                                     repo.find("reminders"))
    by_e: dict[str, list[dict]] = {}
    by_r: dict[str, list[dict]] = {}
    for e in entries:
        by_e.setdefault(e["customer_id"], []).append(e)
    for r in reminders:
        by_r.setdefault(r["customer_id"], []).append(r)
    out = [await to_api(repo, c, by_e.get(c["_id"], []), by_r.get(c["_id"], [])) for c in custs]
    return sorted(out, key=lambda c: -c["balance_paise"])


async def create(repo: MerchantScopedRepo, name: str, phone: str | None, aliases: list[str]) -> dict:
    key = name_key(name)
    if not key:
        raise AppError("validation_error", 422, "Name is required.", {"fields": [{"loc": ["name"]}]})
    if await repo.find_one("customers", {"name_key": key}):
        raise AppError("duplicate_customer", 409, f"{name} pehle se khate mein hai.")
    return await repo.insert("customers", {"name": name.strip(), "name_key": key, "aliases": aliases,
                                           "phone_e164": phone, "balance_paise": 0, "do_not_remind": False,
                                           "created_at": clock.now()})


async def match(repo: MerchantScopedRepo, spoken: str) -> dict:
    """rapidfuzz token_set_ratio over name + aliases: ≥85 matched, 60–84 ambiguous, <60 new."""
    key = name_key(spoken)
    scored = []
    for c in await repo.find("customers"):
        best = max(fuzz.token_set_ratio(key, name_key(n)) for n in [c["name"], *c.get("aliases", [])])
        scored.append({"customer_id": c["_id"], "name": c["name"], "score": round(best)})
    scored.sort(key=lambda x: -x["score"])
    top = scored[0] if scored else None
    if top and top["score"] >= 85 and (len(scored) == 1 or scored[1]["score"] < top["score"]):
        return {"status": "matched", "customer_id": top["customer_id"], "name": top["name"], "candidates": []}
    cands = [s for s in scored if s["score"] >= 60][:3]
    if cands:
        return {"status": "ambiguous", "customer_id": None, "name": spoken, "candidates": cands}
    return {"status": "new", "customer_id": None, "name": spoken, "candidates": []}
