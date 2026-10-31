from fastapi import APIRouter, Depends, Header, Request, Response
from fastapi.responses import JSONResponse

from ..auth import repo_dep
from ..config import get_settings
from ..db import MerchantScopedRepo, get_db
from ..models import PaymentLinkReq
from ..services import idempotency, payments

router = APIRouter()


@router.post("/v1/payment-links", status_code=201)
async def create_payment_link(req: PaymentLinkReq, response: Response, repo: MerchantScopedRepo = Depends(repo_dep),
                              idempotency_key: str | None = Header(None)):
    async def do():
        return payments.link_api(await payments.create_link(repo, req.customer_id, req.amount_paise, idempotency_key))

    status, body = await idempotency.run(get_db(), repo.merchant_id, "payment-links", idempotency_key,
                                         req.model_dump(), do)
    response.status_code = status
    return body


@router.get("/public/pay/{link_id}")
async def pay_view(link_id: str):
    return await payments.public_view(link_id)


@router.post("/public/pay/{link_id}/pay")
async def pay_now(link_id: str):
    return await payments.mock_checkout(link_id)


@router.post("/v1/webhooks/payment")
async def payment_webhook(request: Request, x_signature: str | None = Header(None)):
    return await payments.handle_webhook(await request.body(), x_signature)


@router.get("/healthz")
async def healthz():
    try:
        await get_db().command("ping")
        mongo = "ok"
    except Exception:  # noqa: BLE001
        mongo = "down"
    s = get_settings()
    body = {"status": "ok" if mongo == "ok" else "degraded", "mongo": mongo, "version": "dev",
            "ai_provider": s.ai_provider, "stt": "sarvam" if s.sarvam_api_key else "fake"}
    return JSONResponse(body, status_code=200 if mongo == "ok" else 503)
