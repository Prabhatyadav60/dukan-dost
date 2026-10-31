"""Demo seed (spec §12). `python -m app.seed` drops the database and restores the exact demo state."""
import asyncio
import random
from datetime import date, datetime, timedelta

from . import clock
from .config import get_settings
from .db import MerchantScopedRepo, create_indexes, get_db, new_id

COLLECTIONS = ["cash_receipts", "images", "tts_cache", "merchants", "customers", "ledger_entries", "expenses", "transactions", "cash_logs", "payment_links",
               "reminders", "forecasts", "loan_offers", "events", "thread_messages", "idempotency", "webhook_events",
               "shelf_scans"]


def at_ist(d: date, hour: int = 11) -> datetime:
    return clock.ist_midnight_utc(d) + timedelta(hours=hour)


PAYERS = [("Ankit Sharma", "ankit.sharma@ptyes"), ("Pooja Verma", "pooja.v@ptaxis"), ("Rahul Gupta", "rahulg@ptsbi"),
          ("Neha Singh", "nehasingh@pthdfc"), ("Vikas Yadav", "vikas.yadav@ptyes"), ("Sunita Devi", "sunitadevi@ptaxis"),
          ("Mohd Arif", "arif.m@ptsbi"), ("Kavita Joshi", "kavita.j@pthdfc"), ("Deepak Kumar", "deepakk@ptyes"),
          ("Priya Mishra", "priya.mishra@ptaxis"), ("Rohit Jain", "rohitjain@ptsbi"), ("Anjali Rawat", "anjali.r@pthdfc")]


def payer_for(rng: random.Random) -> dict:
    # regulars pay more often than walk-ins
    name, vpa = PAYERS[min(int(rng.expovariate(0.35)), len(PAYERS) - 1)]
    return {"payer_name": name, "payer_vpa": vpa}


def split(total: int, rng: random.Random) -> list[int]:
    n = rng.randint(8, 14)
    cuts = sorted(rng.sample(range(1, total // 100), n - 1))
    parts = [b - a for a, b in zip([0, *cuts], [*cuts, total // 100])]
    return [p * 100 for p in parts]


async def seed(db=None) -> str:
    db = db or get_db()
    for c in COLLECTIONS:
        await db[c].delete_many({})
    await create_indexes(db)
    s = get_settings()
    today = clock.today_ist()
    rng = random.Random(42)
    mid = new_id()
    await db.merchants.insert_one({
        "_id": mid, "shop_name": "Ramesh Kirana", "owner_name": "Ramesh", "phone": s.demo_phone,
        "upi_vpa": "rameshkirana@paytm", "consent": {"data_use": True, "at": clock.now()},
        "cash_share_estimate": 0.30, "cash_on_hand_paise": 4_340_000,
        "cash_on_hand_at": clock.ist_midnight_utc(today), "created_at": clock.now()})
    repo = MerchantScopedRepo(db, mid)

    txns, logs = [], []
    for i in range(60, -1, -1):
        d = today - timedelta(days=i)
        qr, cash = (890_000, 358_000) if i == 0 else (875_000, 375_000)
        for amt in split(qr, rng):
            ts = clock.ist_midnight_utc(d) + timedelta(hours=8, minutes=rng.randint(0, 12 * 60))
            txns.append({"_id": new_id(), "merchant_id": mid, "amount_paise": amt, "channel": "qr", "ts": ts,
                         **payer_for(rng)})
        logs.append({"_id": new_id(), "merchant_id": mid, "date": d.isoformat(), "amount_paise": cash,
                     "source": "voice", "created_at": at_ist(d, 21)})
    await db.transactions.insert_many(txns)
    await db.cash_logs.insert_many(logs)

    phones = [p.strip() for p in s.demo_customer_phones.split(",") if p.strip()]
    phones += [f"+9190000000{n}" for n in range(11, 15)][len(phones):]
    y = today.year
    people = [
        ("Sharma ji", phones[0], [("credit", 80_000, date(y, 10, 12), ["Doodh", "Atta"])]),
        ("Gupta ji", phones[1], [("credit", 240_000, date(y, 10, 1), ["Chawal", "Dal"]),
                                 ("credit", 200_000, date(y, 10, 15), ["Tel", "Chini"]),
                                 ("payment", 100_000, date(y, 10, 28), [])]),
        ("Verma ji", phones[2], [("credit", 215_000, date(y, 10, 28), ["Atta", "Biscuit"])]),
        ("Anil", phones[3], [("credit", 100_000, date(y, 8, 1), []), ("payment", 100_000, date(y, 9, 5), []),
                             ("credit", 120_000, date(y, 8, 10), []), ("payment", 120_000, date(y, 9, 20), []),
                             ("credit", 220_000, date(y, 9, 20), ["Rashan"])]),
    ]
    from .services.customers import name_key
    for name, phone, entries in people:
        balance = sum(a if t == "credit" else -a for t, a, _, _ in entries)
        c = await repo.insert("customers", {"name": name, "name_key": name_key(name), "aliases": [],
                                            "phone_e164": phone, "balance_paise": balance, "do_not_remind": False,
                                            "created_at": at_ist(date(y, 7, 1))})
        for i, (t, amt, d, items) in enumerate(entries):
            # same-day credit+payment: payment first so FIFO settles the older credit
            hour = 18 if t == "credit" else 10
            await repo.insert("ledger_entries", {
                "customer_id": c["_id"], "type": t, "amount_paise": amt, "items": items,
                "source": "pay_link" if (name == "Gupta ji" and t == "payment") else "manual",
                "transcript": None, "idempotency_key": f"seed-{c['_id']}-{i}", "created_at": at_ist(d, hour)})

    await repo.insert("thread_messages", {"role": "assistant", "kind": "text",
                                          "text": "Namaste Ramesh ji! Bolkar udhaar ya kharcha likhwaiye.",
                                          "ref": None, "created_at": clock.ist_midnight_utc(today)})
    return mid


async def backfill_payers(db=None) -> int:
    """Give payer names to QR payments that have none, without touching anything else."""
    db = db or get_db()
    rng = random.Random(7)
    n = 0
    async for t in db.transactions.find({"payer_name": {"$exists": False}}, {"_id": 1}):
        await db.transactions.update_one({"_id": t["_id"]}, {"$set": payer_for(rng)})
        n += 1
    return n


if __name__ == "__main__":
    import sys
    if "--backfill-payers" in sys.argv:
        print(f"Added payer names to {asyncio.run(backfill_payers())} QR payments.")
    else:
        asyncio.run(seed())
        print("Seeded demo merchant Ramesh Kirana (login +919999900001 / 123456).")
