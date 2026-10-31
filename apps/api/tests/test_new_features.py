"""Unified chat questions, paid/unpaid bills in the forecast, shelf history, Paytm pay links."""
from datetime import timedelta

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 100


async def test_question_gets_answer_in_thread(client):
    r = (await client.post("/v1/voice/parse", data={"text": "Kis ka udhaar sabse zyada hai?"})).json()
    assert r["kind"] == "answer" and r["draft"] is None
    assert "Gupta ji" in r["answer"] and "₹3,400" in r["answer"]
    msgs = (await client.get("/v1/thread")).json()["messages"]
    assert msgs[-2]["role"] == "merchant" and msgs[-1]["text"] == r["answer"]


async def test_entry_still_drafts(client):
    r = (await client.post("/v1/voice/parse", data={"text": "Sharma ji 450 udhaar"})).json()
    assert r["kind"] == "draft" and r["draft"]["intent"] == "credit"


async def _bill(client, key, status, due="2026-11-05"):
    return await client.post("/v1/expenses", headers=key(), json={
        "vendor": "Balaji Traders", "total_paise": 1840000, "due_date": due, "category": "stock",
        "source": "bill_scan", "status": status})


async def test_paid_bill_reduces_cash_unpaid_is_due(client, key):
    base = (await client.get("/v1/forecast")).json()
    assert base["breakdown"]["spent_paise"] == 0 and base["bills"] == []
    paid = (await _bill(client, key, "paid")).json()
    assert paid["status"] == "paid" and paid["due_date"] is None
    f = (await client.get("/v1/forecast")).json()
    assert f["breakdown"]["spent_paise"] == 1840000
    assert f["cash_available_paise"] == base["cash_available_paise"] - 1840000


async def test_marking_bill_paid_keeps_forecast_consistent(client, key):
    e = (await _bill(client, key, "unpaid")).json()
    f1 = (await client.get("/v1/forecast")).json()
    assert [b["id"] for b in f1["bills"]] == [e["id"]] and f1["gap_paise"] == 1500000
    assert (await client.patch(f"/v1/expenses/{e['id']}", json={"status": "paid"})).json()["status"] == "paid"
    f2 = (await client.get("/v1/forecast")).json()
    assert f2["bills"] == [] and f2["breakdown"]["dues_paise"] == 0 and f2["breakdown"]["spent_paise"] == 1840000
    assert f2["gap_paise"] == 1500000  # money moved from "due" to "spent", same shortfall


async def test_shelf_first_tips_then_compare(client):
    from app.db import get_db
    assert (await client.get("/v1/shelf/latest")).status_code == 204
    first = (await client.post("/v1/shelf/scan", files={"image": ("s.jpg", JPEG, "image/jpeg")})).json()
    assert first["first_scan"] and all(f["status"] == "tip" for f in first["findings"])
    # pretend that photo was taken yesterday
    scans = get_db().shelf_scans
    doc = await scans.find_one({"_id": first["scan_id"]})
    await scans.update_one({"_id": doc["_id"]}, {"$set": {"created_at": doc["created_at"] - timedelta(days=1)}})
    second = (await client.post("/v1/shelf/scan", files={"image": ("s.jpg", JPEG, "image/jpeg")})).json()
    assert not second["first_scan"] and second["compared_with_dates"] == ["2026-10-30"]
    assert any(f["status"] == "restock" for f in second["findings"])
    assert (await client.get("/v1/home/summary")).json()["restock_sections"] == 2
    latest = (await client.get("/v1/shelf/latest")).json()
    assert latest["scan_id"] == second["scan_id"]


async def test_pay_link_uses_app_origin_and_mentions_paytm(client):
    origin = "https://demo-shop.ngrok-free.app"
    plan = (await client.post("/v1/reminders/plan", headers={"Origin": origin})).json()["reminders"]
    r = next(x for x in plan if x["customer"]["name"] == "Sharma ji")
    assert r["payment_link"]["url"].startswith(origin + "/pay/")
    assert "Paytm" in r["message"] and "localhost" not in r["message"]
