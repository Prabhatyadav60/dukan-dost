from datetime import datetime

from .. import clock
from ..db import MerchantScopedRepo
from ..money import format_paise
from . import customers, events, thread


def entry_api(e: dict) -> dict:
    return {"id": e["_id"], "customer_id": e["customer_id"], "type": e["type"], "amount_paise": e["amount_paise"],
            "items": e.get("items", []), "source": e["source"], "transcript": e.get("transcript"),
            "created_at": clock.iso(e["created_at"])}


async def add_entry(repo: MerchantScopedRepo, customer_id: str, type_: str, amount_paise: int,
                    items: list[str], source: str, transcript: str | None = None,
                    idempotency_key: str | None = None, created_at: datetime | None = None,
                    announce: bool = True) -> tuple[dict, dict]:
    c = await customers.load(repo, customer_id)
    entry = await repo.insert("ledger_entries", {
        "customer_id": customer_id, "type": type_, "amount_paise": amount_paise, "items": items, "source": source,
        "transcript": transcript, "idempotency_key": idempotency_key, "created_at": created_at or clock.now()})
    delta = amount_paise if type_ == "credit" else -amount_paise
    # Single-document $inc keeps the balance consistent with the entry log.
    await repo.update("customers", {"_id": customer_id}, {"$inc": {"balance_paise": delta}})
    c["balance_paise"] += delta
    if announce:
        await events.log(repo, "entry_saved", entry["_id"], type=type_, source=source)
        if type_ == "credit":
            text = f"Likh diya. {c['name']} ka total ab {format_paise(c['balance_paise'])}."
        else:
            text = f"{c['name']} se {format_paise(amount_paise)} mil gaye. Baaki {format_paise(c['balance_paise'])}."
        await thread.add(repo, "assistant", "text", text, {"type": "ledger_entry", "id": entry["_id"]})
    return entry, c
