import time

from fastapi import Depends

from .auth import consented_merchant
from .config import get_settings
from .errors import AppError

_buckets: dict[str, tuple[float, float]] = {}


async def ai_rate_limit(merchant: dict = Depends(consented_merchant)) -> None:
    """In-process token bucket per merchant (single API instance in this build)."""
    rate = get_settings().ai_rate_limit_per_min
    now = time.monotonic()
    tokens, last = _buckets.get(merchant["_id"], (float(rate), now))
    tokens = min(rate, tokens + (now - last) * rate / 60)
    if tokens < 1:
        raise AppError("rate_limited", 429, "Thoda ruk kar dobara koshish karein.",
                       headers={"Retry-After": str(int((1 - tokens) * 60 / rate) + 1)})
    _buckets[merchant["_id"]] = (tokens - 1, now)
