"""Mock Paytm Payment Links: unguessable ids, our own pay page, HMAC-signed webhook payloads."""
import hashlib
import hmac
import json
import secrets

from .. import clock
from ..config import get_settings


def sign(raw: bytes) -> str:
    return hmac.new(get_settings().payment_webhook_secret.encode(), raw, hashlib.sha256).hexdigest()


def verify(raw: bytes, signature: str | None) -> bool:
    return bool(signature) and hmac.compare_digest(sign(raw), signature)


class MockPaytm:
    def new_link_id(self) -> str:
        return secrets.token_urlsafe(16)

    def link_url(self, link_id: str, base_url: str | None = None) -> str:
        return f"{(base_url or get_settings().public_web_url).rstrip('/')}/pay/{link_id}"

    def webhook_payload(self, link: dict) -> tuple[bytes, str]:
        raw = json.dumps({"event_id": f"evt_{secrets.token_hex(8)}", "link_id": link["_id"],
                          "amount_paise": link["amount_paise"], "status": "paid",
                          "paid_at": clock.iso(clock.now())}).encode()
        return raw, sign(raw)


provider = MockPaytm()
