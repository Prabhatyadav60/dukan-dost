import hashlib
import json
from collections.abc import Awaitable, Callable
from typing import Any

from .. import clock
from ..errors import AppError


async def run(db, merchant_id: str, route: str, key: str | None, body: Any,
              fn: Callable[[], Awaitable[dict]]) -> tuple[int, dict]:
    """Same key + same body → original response (200); different body → 409."""
    if not key:
        raise AppError("idempotency_key_required", 400, "Idempotency-Key header is required.")
    _id = f"{merchant_id}:{route}:{key}"
    body_hash = hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()
    prior = await db.idempotency.find_one({"_id": _id})
    if prior:
        if prior["body_hash"] != body_hash:
            raise AppError("idempotency_conflict", 409, "This Idempotency-Key was used with a different request.")
        return 200, prior["response"]
    response = await fn()
    await db.idempotency.insert_one({"_id": _id, "body_hash": body_hash, "response": response,
                                     "created_at": clock.now()})
    return 201, response
