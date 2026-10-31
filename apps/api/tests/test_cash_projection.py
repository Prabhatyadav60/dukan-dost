"""Cash projection: every unpaid bill counts on its own date; the lowest balance is the shortfall."""
from datetime import date, timedelta

from app.services import forecast

TODAY = date(2026, 10, 31)


def inputs(bills, cash=4340000, received=0, collectible=900000, festivals=None):
    hist = {TODAY - timedelta(days=i): 1250000 for i in range(1, 29)}
    return forecast.ForecastInputs(
        today=TODAY, horizon=14, daily_totals=hist,
        festivals=forecast.load_festivals() if festivals is None else festivals,
        cash_on_hand_paise=cash, received_paise=received, unpaid_bills=bills, collectible_paise=collectible)


def test_demo_numbers():
    r = forecast.compute(inputs([forecast.Bill(1840000, date(2026, 11, 5), "Balaji Traders", "b1")]))
    assert (r["stock_needed_paise"], r["cash_available_paise"], r["gap_paise"]) == (4500000, 3000000, 1500000)
    assert r["plan"] == {"collect_paise": 900000, "loan_paise": 600000}
    assert r["shortfall_date"] == date(2026, 11, 4)


def test_bills_after_the_festival_now_count():
    # the user's real case: a big bill on 17 Nov used to be ignored ("Koi kami nahi")
    bills = [forecast.Bill(252200, date(2026, 10, 6), "Fresh Express", "a"),
             forecast.Bill(3300300, date(2026, 11, 11), "tata", "b"),
             forecast.Bill(8925000, date(2026, 11, 17), "Sunrise Foods", "c")]
    r = forecast.compute(inputs(bills, received=220000))
    assert r["gap_paise"] > 0 and r["shortfall_date"] == date(2026, 11, 17)
    assert r["plan"]["loan_paise"] == r["gap_paise"] - r["plan"]["collect_paise"] > 0
    assert r["counted_bill_ids"] == {"a", "b", "c"}
    labels = [e["label"] for t in r["timeline"] for e in t["events"]]
    assert "Fresh Express (overdue)" in labels and "tata" in labels and "Sunrise Foods" in labels
    first = r["timeline"][0]
    assert first["date"] == date(2026, 11, 1) and first["events"][0]["kind"] == "overdue_bills"


def test_bills_alone_can_need_a_loan_without_festival():
    r = forecast.compute(inputs([forecast.Bill(6000000, date(2026, 11, 3), "Big Distributor", "x")],
                                cash=1000000, festivals=[]))
    assert r["festival"] is None and r["stock_needed_paise"] == 0
    assert r["gap_paise"] > 0 and r["shortfall_date"] == date(2026, 11, 3)


def test_bill_beyond_30_days_not_counted():
    r = forecast.compute(inputs([forecast.Bill(9999900, date(2026, 12, 25), "Later", "z")]))
    assert r["gap_paise"] == 0 and r["counted_bill_ids"] == set()


async def test_forecast_api_exposes_timeline_and_bill_flags(client, key):
    await client.post("/v1/expenses", headers=key(), json={
        "vendor": "Old Supplier", "total_paise": 100000, "due_date": "2026-10-20", "category": "stock",
        "source": "manual", "status": "unpaid"})
    f = (await client.get("/v1/forecast")).json()
    assert f["bills"][0]["overdue"] and f["bills"][0]["counted"]
    assert f["timeline"] and f["low_point"]["date"]
    home = (await client.get("/v1/home/summary")).json()
    assert home["bills_due"][0]["overdue"] is True


async def test_home_alert_says_why(client, key):
    await client.post("/v1/expenses", headers=key(), json={
        "vendor": "Balaji Traders", "total_paise": 1840000, "due_date": "2026-11-05", "category": "stock",
        "source": "bill_scan", "status": "unpaid"})
    assert (await client.get("/v1/home/summary")).json()["alert"]["reason"] == "stock"
    await client.post("/v1/expenses", headers=key(), json={
        "vendor": "Sunrise", "total_paise": 9000000, "due_date": "2026-11-17", "category": "stock",
        "source": "bill_scan", "status": "unpaid"})
    alert = (await client.get("/v1/home/summary")).json()["alert"]
    # money first runs short before Diwali stock; the deepest point is the big bill on 17 Nov
    assert alert["reason"] == "bills" and alert["by_date"] == "2026-11-04"
    assert alert["message"].startswith("4 Nov se kami shuru, 17 Nov tak kul ")
    f = (await client.get("/v1/forecast")).json()
    assert f["explanation"].startswith("17 Nov tak Sunrise ka ₹90,000 ka bill chukane ke liye")
