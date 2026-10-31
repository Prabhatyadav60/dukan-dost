"""'Cash mila' button and the Aaj ki bikri drill-down."""


async def _cust(client, name):
    return next(c for c in (await client.get("/v1/customers")).json()["customers"] if c["name"] == name)


async def test_sales_today_breakdown_by_payer(client):
    s = (await client.get("/v1/sales/today")).json()
    assert s["total_paise"] == 1248000 and s["qr_paise"] == 890000 and s["cash_paise"] == 358000
    assert sum(q["amount_paise"] for q in s["qr"]) == 890000
    assert all(q["payer_name"] and q["payer_vpa"] for q in s["qr"])
    assert sum(g["amount_paise"] for g in s["by_payer"]) == 890000
    assert s["by_payer"] == sorted(s["by_payer"], key=lambda g: -g["amount_paise"])
    assert s["cash_unitemised_paise"] == 358000 and s["udhaar_repaid"] == []


async def test_cash_sale_adds_to_today(client, key):
    r = await client.post("/v1/cash/receipts", headers=key(), json={"amount_paise": 50000, "kind": "sale",
                                                                    "note": "Doodh wale bhaiya"})
    assert r.status_code == 201 and r.json()["today_cash_paise"] == 408000
    home = (await client.get("/v1/home/summary")).json()
    assert home["sales"]["total_paise"] == 1298000 and home["sales"]["cash_source"] == "logged"
    s = (await client.get("/v1/sales/today")).json()
    assert s["cash"][0]["note"] == "Doodh wale bhaiya" and s["cash_unitemised_paise"] == 358000
    assert any(g["channel"] == "cash" and g["name"] == "Doodh wale bhaiya" for g in s["by_payer"])


async def test_cash_sale_on_a_day_without_log(client, key):
    from app.db import get_db
    await get_db().cash_logs.delete_many({"date": "2026-10-31"})
    r = await client.post("/v1/cash/receipts", headers=key(), json={"amount_paise": 50000, "kind": "sale"})
    assert r.status_code == 201 and r.json()["today_cash_paise"] == 50000
    assert (await client.get("/v1/home/summary")).status_code == 200


async def test_udhaar_repaid_in_cash(client, key):
    verma = await _cust(client, "Verma ji")
    r = await client.post("/v1/cash/receipts", headers=key(), json={"amount_paise": 30000, "kind": "udhaar",
                                                                    "customer_id": verma["id"]})
    assert r.status_code == 201 and r.json()["customer"]["balance_paise"] == verma["balance_paise"] - 30000
    s = (await client.get("/v1/sales/today")).json()
    assert s["udhaar_repaid"][0]["customer_name"] == "Verma ji" and s["udhaar_repaid"][0]["source"] == "cash"
    assert s["total_paise"] == 1248000  # repayment is not a sale
    bad = await client.post("/v1/cash/receipts", headers=key(), json={"amount_paise": 100, "kind": "udhaar"})
    assert bad.status_code == 422


async def test_cash_receipt_idempotent(client, key):
    k = key()
    body = {"amount_paise": 20000, "kind": "sale"}
    assert (await client.post("/v1/cash/receipts", headers=k, json=body)).status_code == 201
    assert (await client.post("/v1/cash/receipts", headers=k, json=body)).status_code == 200
    assert (await client.get("/v1/home/summary")).json()["sales"]["cash_paise"] == 378000
