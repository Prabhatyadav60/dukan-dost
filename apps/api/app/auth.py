import calendar
from datetime import timedelta

import jwt
from fastapi import Depends, Header

from . import clock
from .config import get_settings
from .db import MerchantScopedRepo, get_db
from .errors import AppError


def verify_otp(phone: str, otp: str) -> bool:
    """Provider seam for real OTP; this build accepts only the demo login."""
    s = get_settings()
    return phone == s.demo_phone and otp == s.demo_otp


def issue_token(merchant_id: str) -> tuple[str, str]:
    s = get_settings()
    iat = clock.now()
    exp = iat + timedelta(minutes=s.jwt_ttl_minutes)
    token = jwt.encode({"sub": merchant_id, "iat": iat, "exp": exp}, s.jwt_secret, algorithm="HS256")
    return token, clock.iso(exp)


def _unauth() -> AppError:
    return AppError("unauthenticated", 401, "Please log in again.")


async def current_merchant(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise _unauth()
    try:
        # demo clock may run ahead/behind real time, so verify exp against our own clock
        claims = jwt.decode(authorization[7:], get_settings().jwt_secret, algorithms=["HS256"],
                            options={"verify_exp": False, "verify_iat": False})
    except jwt.PyJWTError:
        raise _unauth()
    if claims.get("exp", 0) < calendar.timegm(clock.now().utctimetuple()):
        raise _unauth()
    merchant = await get_db().merchants.find_one({"_id": claims.get("sub")})
    if not merchant:
        raise _unauth()
    return merchant


async def consented_merchant(merchant: dict = Depends(current_merchant)) -> dict:
    if not (merchant.get("consent") or {}).get("data_use"):
        raise AppError("consent_required", 403, "Data-use consent is required before using this feature.")
    return merchant


async def repo_dep(merchant: dict = Depends(consented_merchant)) -> MerchantScopedRepo:
    return MerchantScopedRepo(get_db(), merchant["_id"])


def merchant_api(m: dict) -> dict:
    return {"id": m["_id"], "shop_name": m["shop_name"], "owner_name": m["owner_name"], "phone": m["phone"],
            "consent_given": bool((m.get("consent") or {}).get("data_use")),
            "cash_share_estimate": m.get("cash_share_estimate", 0.3),
            "cash_on_hand_paise": m.get("cash_on_hand_paise", 0)}
