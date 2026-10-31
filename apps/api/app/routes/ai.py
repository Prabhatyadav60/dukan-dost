import os
import re

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile

from .. import clock
from ..agents import cash_advisor
from ..ai import get_llm, get_stt
from ..auth import consented_merchant, repo_dep
from ..config import get_settings
from ..db import MerchantScopedRepo
from ..errors import AppError, not_found
from ..ratelimit import ai_rate_limit
from ..services import assistant, customers, events, media, payments, reminders, shelf, thread

router = APIRouter(prefix="/v1")

QUESTION_START = re.compile(
    r"^(kya|kitna|kitne|kitni|kaun|kaunsa|kis|kise|kab|kaise|kahan|kyun|kyon|what|how|who|when|which|why|batao|bataiye)\b",
    re.IGNORECASE)


def looks_like_question(text: str) -> bool:
    t = text.strip()
    return t.endswith(("?", "؟")) or bool(QUESTION_START.match(t))


EXPENSE_DEFAULT_VENDOR = {"rent": "Kiraya", "staff": "Staff", "stock": "Maal", "other": "Kharcha"}


@router.post("/voice/parse", dependencies=[Depends(ai_rate_limit)])
async def voice_parse(audio: UploadFile | None = File(None), text: str | None = Form(None, max_length=300),
                      m: dict = Depends(consented_merchant), repo: MerchantScopedRepo = Depends(repo_dep)):
    if audio is None and not (text and text.strip()):
        raise AppError("validation_error", 422, "Send audio or text.", {"fields": [{"loc": ["audio"]}]})
    if audio is not None:
        wav = await media.to_wav(await audio.read(), audio.filename or "", audio.content_type or "")
        try:
            transcript = await get_stt().transcribe(wav, audio.filename or "voice")
        finally:
            os.unlink(wav)  # audio is never kept
        kind = "voice"
    else:
        transcript, kind = text.strip(), "text"
    if not transcript.strip():
        raise AppError("validation_error", 422, "Awaaz samajh nahi aayi. Dobara bolein ya likh kar bhejein.")
    await thread.add(repo, "merchant", kind, transcript)
    if looks_like_question(transcript):  # skip the classifier round trip for obvious questions
        draft = None
    else:
        draft = await get_llm().parse_entry(transcript, clock.today_ist().isoformat())
    if draft is None or draft.intent == "question":
        reply = await assistant.answer(repo, m, transcript)
        return {"kind": "answer", "transcript": transcript, "answer": reply, "draft": None,
                "customer_match": None, "warnings": []}
    if draft.intent == "expense" and not (draft.vendor or "").strip():
        # "rent 8000 diya" names no payee; give the confirm sheet a saveable default the owner can edit
        draft.vendor = EXPENSE_DEFAULT_VENDOR[draft.category or "other"]
    warnings = []
    if not draft.amount_paise:
        warnings.append("amount_missing")
    if draft.confidence < 0.8:
        warnings.append("low_confidence")
    match = {"status": "not_applicable", "customer_id": None, "name": draft.customer_name, "candidates": []}
    if draft.intent in ("credit", "payment"):
        if draft.customer_name:
            match = await customers.match(repo, draft.customer_name)
        else:
            match = {"status": "new", "customer_id": None, "name": "", "candidates": []}
        if match["status"] != "matched":
            warnings.append("customer_unknown")
    return {"kind": "draft", "transcript": transcript, "answer": None, "draft": draft.model_dump(),
            "customer_match": match, "warnings": warnings}


@router.post("/bills/scan", dependencies=[Depends(ai_rate_limit)])
async def bills_scan(images: list[UploadFile] = File(...), repo: MerchantScopedRepo = Depends(repo_dep)):
    if not 1 <= len(images) <= 3:
        raise AppError("validation_error", 422, "1 se 3 photo bhejein.", {"fields": [{"loc": ["images"]}]})
    blobs, keys = [], []
    for img in images:
        data = await img.read()
        mt, ext = media.sniff_image(data)
        blobs.append((mt, data))
        keys.append(await media.save_image(repo, "bills", data, ext, mt))
    await thread.add(repo, "merchant", "photo", f"Bill photo · {len(images)} page" + ("s" if len(images) > 1 else ""))
    draft = await get_llm().read_bill(blobs)
    line_sum = sum(li.amount_paise for li in draft.line_items)
    total = draft.total_paise or 0
    diff = line_sum - total
    ok = total > 0 and abs(diff) <= max(100, round(total * 0.01))
    if not ok:
        await events.log(repo, "bill_sum_mismatch", None, difference_paise=diff)
    return {"draft": draft.model_dump(), "image_keys": keys,
            "checks": {"sum_matches": ok, "line_items_sum_paise": line_sum, "difference_paise": diff}}


def _forecast_api(doc: dict) -> dict:
    return {"forecast_id": doc["_id"], "generated_at": clock.iso(doc["generated_at"]),
            "horizon_days": doc["horizon_days"], "festival": doc["festival"], "buy_by_date": doc["buy_by_date"],
            "daily": [{k: d[k] for k in ("date", "baseline_paise", "uplift", "forecast_paise")} for d in doc["daily"]],
            "stock_needed_paise": doc["stock_needed_paise"], "cash_available_paise": doc["cash_available_paise"],
            "gap_paise": doc["gap_paise"], "plan": doc["plan"], "explanation": doc["explanation"],
            "assumptions": doc["assumptions"], "breakdown": doc.get("breakdown")}


@router.get("/forecast")
async def get_forecast(horizon: int = Query(14, ge=7, le=30), m: dict = Depends(consented_merchant),
                       repo: MerchantScopedRepo = Depends(repo_dep)):
    doc = await cash_advisor.run(repo, m, horizon)
    bills = await repo.find("expenses", {"status": "unpaid"}, sort=[("due_date", 1)])
    return {**_forecast_api(doc), "bills": [
        {"id": e["_id"], "vendor": e["vendor"], "total_paise": e["total_paise"], "due_date": e.get("due_date"),
         "status": e["status"]} for e in bills]}


def _offer_api(o: dict) -> dict:
    return {"offer_id": o["_id"], "amount_paise": o["amount_paise"], "reason": o["reason"],
            "forecast_id": o["forecast_id"], "status": o["status"], "disclaimer": "Subject to lender approval"}


@router.get("/loan-offer")
async def loan_offer(repo: MerchantScopedRepo = Depends(repo_dep)):
    f = await repo.find_one("forecasts", sort=[("generated_at", -1)])
    if not f or f["plan"]["loan_paise"] <= 0:
        return Response(status_code=204)
    o = await repo.find_one("loan_offers", {"amount_paise": f["plan"]["loan_paise"]}, sort=[("created_at", -1)])
    if not o:
        return Response(status_code=204)
    return _offer_api(o)


@router.post("/loan-offer/{offer_id}/interest")
async def loan_interest(offer_id: str, repo: MerchantScopedRepo = Depends(repo_dep)):
    o = await repo.get("loan_offers", offer_id)
    if not o:
        raise not_found()
    if o["status"] != "interested":
        await repo.update("loan_offers", {"_id": offer_id}, {"$set": {"status": "interested"}})
        await events.log(repo, "offer_interested", offer_id, amount_paise=o["amount_paise"])
    return _offer_api({**o, "status": "interested"})


@router.post("/reminders/plan", dependencies=[Depends(ai_rate_limit)])
async def reminders_plan(request: Request, m: dict = Depends(consented_merchant),
                         repo: MerchantScopedRepo = Depends(repo_dep)):
    base = payments.public_base(request.headers.get("origin"))
    return {"reminders": await reminders.plan(repo, m, base)}


@router.post("/reminders/{reminder_id}/sent")
async def reminder_sent(reminder_id: str, repo: MerchantScopedRepo = Depends(repo_dep)):
    return await reminders.mark_sent(repo, reminder_id)


def _shelf_enabled() -> None:
    if not get_settings().feature_shelf_scan:
        raise AppError("feature_disabled", 404, "Shelf scan is not enabled.")


@router.post("/shelf/scan", dependencies=[Depends(ai_rate_limit), Depends(_shelf_enabled)])
async def shelf_scan(image: UploadFile = File(...), shelf_label: str = Form("main", max_length=40),
                     repo: MerchantScopedRepo = Depends(repo_dep)):
    return await shelf.scan(repo, shelf_label, await image.read())


@router.get("/shelf/latest", dependencies=[Depends(_shelf_enabled)])
async def shelf_latest(shelf_label: str = Query("main", max_length=40), repo: MerchantScopedRepo = Depends(repo_dep)):
    s = await shelf.latest(repo, shelf_label)
    return s if s else Response(status_code=204)
