import json
import re
from datetime import timedelta

from .. import clock
from ..adapters.paytm_mock import provider, verify
from ..config import get_settings
from ..db import MerchantScopedRepo, get_db
from ..errors import AppError, not_found
from ..money import format_paise
from . import customers, events, ledger, thread


def public_base(origin: str | None) -> str:
    """Pay links point at the same web app the merchant is using (e.g. the ngrok HTTPS URL),
    falling back to PUBLIC_WEB_URL for server-side callers."""
    configured = get_settings().public_web_url
    if origin and origin.startswith(("http://", "https://")) and "localhost" not in origin \
            and "127.0.0.1" not in origin:
        return origin
    return configured


def link_api(link: dict, base_url: str | None = None) -> dict:
    return {"id": link["_id"], "url": provider.link_url(link["_id"], base_url), "status": link_status(link),
            "expires_at": clock.iso(link["expires_at"])}


def link_status(link: dict) -> str:
    if link["status"] == "paid":
        return "paid"
    return "expired" if link["expires_at"] <= clock.now() else "created"


async def open_link(repo: MerchantScopedRepo, customer_id: str, amount_paise: int) -> dict | None:
    for link in await repo.find("payment_links", {"customer_id": customer_id, "status": "created"}):
        if link["amount_paise"] == amount_paise and link["expires_at"] > clock.now():
            return link
    return None


async def create_link(repo: MerchantScopedRepo, customer_id: str, amount_paise: int,
                      idempotency_key: str | None = None) -> dict:
    await customers.load(repo, customer_id)
    if amount_paise <= 0:
        raise AppError("validation_error", 422, "Amount must be positive.")
    existing = await open_link(repo, customer_id, amount_paise)
    if existing:
        return existing
    ttl = timedelta(hours=get_settings().pay_link_ttl_hours)
    return await repo.insert("payment_links", {
        "_id": provider.new_link_id(), "customer_id": customer_id, "amount_paise": amount_paise,
        "status": "created", "idempotency_key": idempotency_key, "expires_at": clock.now() + ttl,
        "paid_at": None, "created_at": clock.now()})


async def public_view(link_id: str) -> dict:
    db = get_db()
    link = await db.payment_links.find_one({"_id": link_id})
    if not link:
        raise not_found()
    repo = MerchantScopedRepo(db, link["merchant_id"])
    merchant = await db.merchants.find_one({"_id": link["merchant_id"]})
    c = await customers.load(repo, link["customer_id"])
    f = customers.fifo(await repo.find("ledger_entries", {"customer_id": c["_id"]}))
    items = [{"date": clock.to_ist_date(o["entry"]["created_at"]).isoformat(), "items": o["entry"].get("items", []),
              "amount_paise": o["remaining"]} for o in f["open"]]
    return {"shop_name": merchant["shop_name"], "customer_name": c["name"], "amount_paise": link["amount_paise"],
            "items": items, "status": link_status(link), "expires_at": clock.iso(link["expires_at"])}


async def mock_checkout(link_id: str) -> dict:
    link = await get_db().payment_links.find_one({"_id": link_id})
    if not link:
        raise not_found()
    status = link_status(link)
    if status == "paid":
        raise AppError("link_already_paid", 409, "Yeh link pehle hi pay ho chuka hai.")
    if status == "expired":
        raise AppError("link_expired", 410, "Yeh link expire ho gaya hai.")
    raw, sig = provider.webhook_payload(link)
    await handle_webhook(raw, sig)  # the mock provider "calls" our webhook
    link = await get_db().payment_links.find_one({"_id": link_id})
    return {"status": "paid", "paid_at": clock.iso(link["paid_at"])}


async def handle_webhook(raw: bytes, signature: str | None) -> dict:
    if not verify(raw, signature):
        raise AppError("invalid_signature", 401, "Invalid webhook signature.")
    body = json.loads(raw)
    db = get_db()
    if await db.webhook_events.find_one({"_id": body["event_id"]}):
        return {"ok": True}
    await db.webhook_events.insert_one({"_id": body["event_id"], "received_at": clock.now()})
    link = await db.payment_links.find_one({"_id": body["link_id"]})
    if not link or link["status"] == "paid":
        return {"ok": True}
    # claim the link atomically so concurrent deliveries record the payment once
    res = await db.payment_links.update_one({"_id": link["_id"], "status": {"$ne": "paid"}},
                                            {"$set": {"status": "paid", "paid_at": clock.now()}})
    if res.modified_count == 0:
        return {"ok": True}
    repo = MerchantScopedRepo(db, link["merchant_id"])
    entry, c = await ledger.add_entry(repo, link["customer_id"], "payment", link["amount_paise"], [], "pay_link",
                                      idempotency_key=f"link:{link['_id']}", announce=False)
    await repo.update_many("reminders", {"payment_link_id": link["_id"]}, {"$set": {"status": "paid"}})
    await events.log(repo, "link_paid", link["_id"], amount_paise=link["amount_paise"])
    await thread.add(repo, "assistant", "text",
                     f"{c['name']} ne {format_paise(link['amount_paise'])} pay kar diye.",
                     {"type": "ledger_entry", "id": entry["_id"]})
    return {"ok": True}


def wa_url(phone_e164: str, message: str) -> str:
    from urllib.parse import quote
    digits = re.sub(r"\D", "", phone_e164)
    return f"https://wa.me/{digits}?text={quote(message)}"
