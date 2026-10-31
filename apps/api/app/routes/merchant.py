import asyncio
from datetime import timedelta

from fastapi import APIRouter, Depends, Header, Query, Response

from .. import clock
from ..auth import current_merchant, issue_token, merchant_api, repo_dep, consented_merchant, verify_otp
from ..db import MerchantScopedRepo, get_db
from ..errors import AppError, not_found
from ..models import (CashLogReq, ConsentReq, CustomerCreate, CustomerPatch, ExpensePatch, ExpenseReq,
                      LedgerReq, SessionReq)
from ..money import format_paise
from ..services import cash, customers, events, forecast, idempotency, ledger, thread
from ..config import get_settings

router = APIRouter(prefix="/v1")


@router.post("/auth/session")
async def session(req: SessionReq):
    if not verify_otp(req.phone, req.otp):
        raise AppError("invalid_otp", 401, "Phone ya OTP galat hai.")
    m = await get_db().merchants.find_one({"phone": req.phone})
    if not m:
        raise AppError("invalid_otp", 401, "Phone ya OTP galat hai.")
    token, exp = issue_token(m["_id"])
    return {"access_token": token, "token_type": "bearer", "expires_at": exp, "merchant": merchant_api(m)}


@router.get("/me")
async def me(m: dict = Depends(current_merchant)):
    return merchant_api(m)


@router.post("/onboarding/consent")
async def consent(req: ConsentReq, m: dict = Depends(current_merchant)):
    if not req.data_use:
        raise AppError("validation_error", 422, "Consent is required.", {"fields": [{"loc": ["data_use"]}]})
    now = clock.now()
    upd = {"consent": {"data_use": True, "at": now}, "cash_share_estimate": req.cash_share_estimate,
           "cash_on_hand_paise": req.cash_on_hand_paise, "cash_on_hand_at": now}
    await get_db().merchants.update_one({"_id": m["_id"]}, {"$set": upd})
    return merchant_api({**m, **upd})


@router.get("/home/summary")
async def home(m: dict = Depends(consented_merchant), repo: MerchantScopedRepo = Depends(repo_dep)):
    today = clock.today_ist()
    days, custs, unpaid, inputs = await asyncio.gather(
        cash.daily_sales(repo, m, today, today),
        repo.find("customers", {"balance_paise": {"$gt": 0}}),
        repo.find("expenses", {"status": "unpaid"}, sort=[("due_date", 1)]),
        cash.forecast_inputs(repo, m, 14, get_settings().forecast_margin))
    [day] = days
    due_cutoff = (today + timedelta(days=7)).isoformat()
    bills = [e for e in unpaid if e.get("due_date") and e["due_date"] <= due_cutoff]
    r = forecast.compute(inputs)
    alert = None
    if r["gap_paise"] > 0:
        alert = {"type": "cash_gap", "gap_paise": r["gap_paise"], "by_date": r["buy_by_date"].isoformat(),
                 "message": f"{r['buy_by_date'].strftime('%-d %b')} tak {format_paise(r['gap_paise'])} kam padega"}
    restock = None
    if get_settings().feature_shelf_scan:
        lo, hi = clock.ist_day_range(today)
        scan = await repo.find_one("shelf_scans", {"created_at": {"$gte": lo, "$lt": hi}}, sort=[("created_at", -1)])
        if scan:
            restock = sum(1 for f in scan["findings"] if f["status"] == "restock")
    return {
        "date": today.isoformat(),
        "sales": {"qr_paise": day["qr_paise"], "cash_paise": day["cash_paise"], "cash_source": day["cash_source"],
                  "total_paise": day["qr_paise"] + day["cash_paise"]},
        "udhaar_total_paise": sum(c["balance_paise"] for c in custs),
        "customers_with_balance": len(custs),
        "restock_sections": restock,
        "bills_due": [{"expense_id": e["_id"], "vendor": e["vendor"], "total_paise": e["total_paise"],
                       "due_date": e["due_date"]} for e in bills],
        "alert": alert,
    }


@router.get("/thread")
async def get_thread(limit: int = Query(50, ge=1, le=200), repo: MerchantScopedRepo = Depends(repo_dep)):
    msgs = await repo.find("thread_messages", sort=[("created_at", -1)], limit=limit)
    return {"messages": [thread.to_api(x) for x in reversed(msgs)]}


@router.get("/customers")
async def list_customers(repo: MerchantScopedRepo = Depends(repo_dep)):
    return {"customers": [customers.public(c) for c in await customers.list_api(repo)]}


@router.post("/customers", status_code=201)
async def create_customer(req: CustomerCreate, repo: MerchantScopedRepo = Depends(repo_dep)):
    c = await customers.create(repo, req.name, req.phone_e164, req.aliases)
    return customers.public(await customers.to_api(repo, c))


@router.patch("/customers/{customer_id}")
async def patch_customer(customer_id: str, req: CustomerPatch, repo: MerchantScopedRepo = Depends(repo_dep)):
    await customers.load(repo, customer_id)
    upd = req.model_dump(exclude_unset=True)
    if upd:
        await repo.update("customers", {"_id": customer_id}, {"$set": upd})
    return customers.public(await customers.to_api(repo, await customers.load(repo, customer_id)))


@router.get("/customers/{customer_id}")
async def get_customer(customer_id: str, repo: MerchantScopedRepo = Depends(repo_dep)):
    return customers.public(await customers.to_api(repo, await customers.load(repo, customer_id)))


@router.get("/customers/{customer_id}/entries")
async def customer_entries(customer_id: str, repo: MerchantScopedRepo = Depends(repo_dep)):
    await customers.load(repo, customer_id)
    es = await repo.find("ledger_entries", {"customer_id": customer_id}, sort=[("created_at", -1)])
    return {"entries": [ledger.entry_api(e) for e in es]}


@router.post("/ledger/entries", status_code=201)
async def add_ledger(req: LedgerReq, response: Response, repo: MerchantScopedRepo = Depends(repo_dep),
                     idempotency_key: str | None = Header(None)):
    async def do():
        entry, _ = await ledger.add_entry(repo, req.customer_id, req.type, req.amount_paise, req.items, req.source,
                                          req.transcript, idempotency_key)
        if req.edited:
            await events.log(repo, "entry_edited_before_save", entry["_id"])
        c = await customers.to_api(repo, await customers.load(repo, req.customer_id))
        return {"entry": ledger.entry_api(entry), "customer": customers.public(c)}

    status, body = await idempotency.run(get_db(), repo.merchant_id, "ledger", idempotency_key,
                                         req.model_dump(mode="json"), do)
    response.status_code = status
    return body


def expense_api(e: dict) -> dict:
    return {"id": e["_id"], "vendor": e["vendor"], "line_items": e.get("line_items", []),
            "total_paise": e["total_paise"], "due_date": e.get("due_date"), "category": e["category"],
            "status": e["status"], "source": e["source"], "image_keys": e.get("image_keys", []),
            "created_at": clock.iso(e["created_at"]), "paid_at": clock.iso(e.get("paid_at"))}


@router.post("/expenses", status_code=201)
async def add_expense(req: ExpenseReq, response: Response, repo: MerchantScopedRepo = Depends(repo_dep),
                      idempotency_key: str | None = Header(None)):
    async def do():
        data = req.model_dump(mode="json")
        e = await repo.insert("expenses", {**data, "status": "unpaid", "idempotency_key": idempotency_key,
                                           "created_at": clock.now(), "paid_at": None})
        await events.log(repo, "bill_saved", e["_id"], source=req.source)
        due = ""
        if req.due_date:
            due = f", due {req.due_date.strftime('%-d %b')}"
        text = (f"Bill padh liya: {format_paise(req.total_paise)}{due}." if req.source == "bill_scan"
                else f"Kharcha likh diya: {req.vendor} {format_paise(req.total_paise)}{due}.")
        await thread.add(repo, "assistant", "text", text, {"type": "expense", "id": e["_id"]})
        return expense_api(e)

    status, body = await idempotency.run(get_db(), repo.merchant_id, "expenses", idempotency_key,
                                         req.model_dump(mode="json"), do)
    response.status_code = status
    return body


@router.get("/expenses")
async def list_expenses(status: str | None = Query(None, pattern="^(paid|unpaid)$"),
                        repo: MerchantScopedRepo = Depends(repo_dep)):
    es = await repo.find("expenses", {"status": status} if status else {}, sort=[("created_at", -1)])
    return {"expenses": [expense_api(e) for e in es]}


@router.patch("/expenses/{expense_id}")
async def patch_expense(expense_id: str, req: ExpensePatch, repo: MerchantScopedRepo = Depends(repo_dep)):
    if not await repo.get("expenses", expense_id):
        raise not_found()
    await repo.update("expenses", {"_id": expense_id}, {"$set": {"status": "paid", "paid_at": clock.now()}})
    return expense_api(await repo.get("expenses", expense_id))


@router.post("/cash/logs", status_code=201)
async def cash_log(req: CashLogReq, response: Response, repo: MerchantScopedRepo = Depends(repo_dep),
                   idempotency_key: str | None = Header(None)):
    async def do():
        d = req.date.isoformat()
        await repo.update("cash_logs", {"date": d}, {"$set": {"amount_paise": req.amount_paise, "source": req.source,
                                                              "created_at": clock.now()}}, upsert=True)
        log = await repo.find_one("cash_logs", {"date": d})
        await thread.add(repo, "assistant", "text",
                         f"Aaj ka cash {format_paise(req.amount_paise)} likh liya.", {"type": "cash_log", "id": log["_id"]})
        return {"id": log["_id"], "date": d, "amount_paise": req.amount_paise, "source": req.source}

    status, body = await idempotency.run(get_db(), repo.merchant_id, "cash", idempotency_key,
                                         req.model_dump(mode="json"), do)
    response.status_code = status
    return body


@router.get("/cashflow")
async def cashflow(days: int = Query(30, ge=1, le=90), m: dict = Depends(consented_merchant),
                   repo: MerchantScopedRepo = Depends(repo_dep)):
    to = clock.today_ist()
    frm = to - timedelta(days=days - 1)
    daily = await cash.daily_sales(repo, m, frm, to)
    lo, _ = clock.ist_day_range(frm)
    exps = await repo.find("expenses")
    return {
        "from": frm.isoformat(), "to": to.isoformat(),
        "in": {"qr_paise": sum(d["qr_paise"] for d in daily),
               "cash_logged_paise": sum(d["cash_paise"] for d in daily if d["cash_source"] == "logged"),
               "cash_estimated_paise": sum(d["cash_paise"] for d in daily if d["cash_source"] == "estimated")},
        "out": {"expenses_paid_paise": sum(e["total_paise"] for e in exps
                                           if e["status"] == "paid" and e.get("paid_at") and e["paid_at"] >= lo),
                "expenses_due_paise": sum(e["total_paise"] for e in exps if e["status"] == "unpaid")},
        "owed_to_shop_paise": sum(c["balance_paise"] for c in await repo.find("customers", {"balance_paise": {"$gt": 0}})),
        "daily": [{**d, "date": d["date"].isoformat()} for d in daily],
    }
