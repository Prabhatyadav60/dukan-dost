"""The demo script (spec §17) and the §14 assertions, against the fake AI provider."""
import json

from app.adapters.paytm_mock import sign


async def customer_id(client, name):
    cs = (await client.get("/v1/customers")).json()["customers"]
    return next(c for c in cs if c["name"] == name)["id"]


async def test_home_initial(client):
    h = (await client.get("/v1/home/summary")).json()
    assert h["sales"] == {"qr_paise": 890000, "cash_paise": 358000, "cash_source": "logged", "total_paise": 1248000}
    assert h["udhaar_total_paise"] == 855000
    assert h["alert"] is None


async def test_full_demo(client, key):
    # 1. voice (typed fallback) → draft → confirm
    r = (await client.post("/v1/voice/parse", data={"text": "Sharma ji 450 udhaar, doodh aur atta"})).json()
    d = r["draft"]
    assert (d["intent"], d["amount_paise"], d["items"]) == ("credit", 45000, ["Doodh", "Atta"])
    assert r["customer_match"]["status"] == "matched"
    r = await client.post("/v1/ledger/entries", headers=key(), json={
        "customer_id": r["customer_match"]["customer_id"], "type": "credit", "amount_paise": 45000,
        "items": d["items"], "source": "text", "transcript": r["transcript"]})
    assert r.status_code == 201 and r.json()["customer"]["balance_paise"] == 125000
    assert (await client.get("/v1/home/summary")).json()["udhaar_total_paise"] == 900000

    # 2. bill scan → expense
    jpeg = b"\xff\xd8\xff\xe0" + b"0" * 100
    b = (await client.post("/v1/bills/scan", files={"images": ("bill.jpg", jpeg, "image/jpeg")})).json()
    assert b["checks"]["sum_matches"] and b["draft"]["total_paise"] == 1840000
    r = await client.post("/v1/expenses", headers=key(), json={
        "vendor": b["draft"]["vendor"], "line_items": b["draft"]["line_items"], "total_paise": 1840000,
        "due_date": b["draft"]["due_date"], "category": "stock", "source": "bill_scan", "image_keys": b["image_keys"]})
    assert r.status_code == 201

    # 3. forecast numbers from the deck
    home = (await client.get("/v1/home/summary")).json()
    assert home["alert"]["gap_paise"] == 1500000 and home["alert"]["by_date"] == "2026-11-04"
    f = (await client.get("/v1/forecast")).json()
    assert (f["stock_needed_paise"], f["cash_available_paise"], f["gap_paise"]) == (4500000, 3000000, 1500000)
    assert f["plan"] == {"collect_paise": 900000, "loan_paise": 600000}
    assert "₹45,000" in f["explanation"]
    offer = (await client.get("/v1/loan-offer")).json()
    assert offer["amount_paise"] == 600000

    # 4. reminders: Sharma, Gupta, Anil eligible; Verma too recent
    plan = (await client.post("/v1/reminders/plan")).json()["reminders"]
    by = {x["customer"]["name"]: x for x in plan}
    assert by["Verma ji"]["skipped_reason"] == "too_recent"
    for n in ("Sharma ji", "Gupta ji", "Anil"):
        assert by[n]["skipped_reason"] is None and by[n]["wa_url"].startswith("https://wa.me/")
    sharma = by["Sharma ji"]
    assert "₹1,250" in sharma["message"] and sharma["payment_link"]["url"] in sharma["message"]
    await client.post(f"/v1/reminders/{sharma['reminder_id']}/sent")

    # 5. customer pays via the public link
    link_id = sharma["payment_link"]["id"]
    pub = (await client.get(f"/public/pay/{link_id}")).json()
    assert pub["amount_paise"] == 125000 and pub["shop_name"] == "Ramesh Kirana"
    assert (await client.post(f"/public/pay/{link_id}/pay")).json()["status"] == "paid"
    assert (await client.post(f"/public/pay/{link_id}/pay")).status_code == 409
    assert (await client.get("/v1/home/summary")).json()["udhaar_total_paise"] == 775000

    f = (await client.get("/v1/forecast")).json()
    assert (f["cash_available_paise"], f["gap_paise"]) == (3125000, 1375000)
    assert f["plan"] == {"collect_paise": 775000, "loan_paise": 600000}
    thread = (await client.get("/v1/thread")).json()["messages"]
    assert thread[-1]["text"] == "Sharma ji ne ₹1,250 pay kar diye." or any(
        m["text"] == "Sharma ji ne ₹1,250 pay kar diye." for m in thread)


async def test_ledger_idempotency(client, key):
    cid = await customer_id(client, "Verma ji")
    k = key()
    body = {"customer_id": cid, "type": "payment", "amount_paise": 5000, "source": "manual"}
    assert (await client.post("/v1/ledger/entries", headers=k, json=body)).status_code == 201
    assert (await client.post("/v1/ledger/entries", headers=k, json=body)).status_code == 200
    assert (await client.post("/v1/ledger/entries", headers=k, json={**body, "amount_paise": 6000})).status_code == 409
    entries = (await client.get(f"/v1/customers/{cid}/entries")).json()["entries"]
    assert sum(1 for e in entries if e["type"] == "payment") == 1
    assert (await client.post("/v1/ledger/entries", json=body)).status_code == 400


async def test_webhook_idempotency_and_signature(client, key):
    cid = await customer_id(client, "Anil")
    link = (await client.post("/v1/payment-links", headers=key(),
                              json={"customer_id": cid, "amount_paise": 220000})).json()
    raw = json.dumps({"event_id": "evt_1", "link_id": link["id"], "amount_paise": 220000, "status": "paid",
                      "paid_at": "2026-10-31T10:00:00Z"}).encode()
    assert (await client.post("/v1/webhooks/payment", content=raw, headers={"X-Signature": "bad"})).status_code == 401
    for _ in range(2):
        r = await client.post("/v1/webhooks/payment", content=raw, headers={"X-Signature": sign(raw)})
        assert r.status_code == 200
    cs = (await client.get("/v1/customers")).json()["customers"]
    assert next(c for c in cs if c["id"] == cid)["balance_paise"] == 0


async def test_auth_and_consent(client):
    import httpx
    from app.main import app
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as anon:
        r = await anon.get("/v1/customers")
        assert r.status_code == 401 and r.json()["error"]["code"] == "unauthenticated"
        assert (await anon.post("/v1/auth/session", json={"phone": "+919999900001", "otp": "0"})).status_code == 401


async def test_tenant_isolation(client):
    from app.db import get_db
    from app.auth import issue_token
    await get_db().merchants.insert_one({"_id": "other", "shop_name": "B", "owner_name": "B", "phone": "+910",
                                         "consent": {"data_use": True}})
    cid = await customer_id(client, "Anil")
    token, _ = issue_token("other")
    r = await client.get(f"/v1/customers/{cid}/entries", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404
    assert (await client.get("/v1/customers", headers={"Authorization": f"Bearer {token}"})).json()["customers"] == []


async def test_late_payer(client):
    cs = {c["name"]: c for c in (await client.get("/v1/customers")).json()["customers"]}
    assert cs["Anil"]["late_payer"] and not cs["Gupta ji"]["late_payer"]


async def test_expense_without_vendor_gets_default(client, monkeypatch):
    from app.ai.fake import FakeLLM
    from app.ai.schemas import EntryDraft

    async def no_vendor(self, transcript):
        return EntryDraft(intent="expense", amount_paise=800000, category="rent", confidence=0.9)
    monkeypatch.setattr(FakeLLM, "parse_entry", no_vendor)
    r = (await client.post("/v1/voice/parse", data={"text": "dukaan ka rent 8000 diya"})).json()
    assert r["draft"]["vendor"] == "Kiraya"
