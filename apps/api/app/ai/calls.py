"""One wrapper for every model call: timeout, retries on transient errors only, metadata-only logging."""
import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

import httpx
import structlog

from ..errors import AppError

log = structlog.get_logger()
T = TypeVar("T")

TIMEOUTS = {"speech": 8.0, "vision": 20.0, "text": 10.0, "tts": 10.0}
BACKOFF = (0.5, 1.5)


def _transient(exc: Exception) -> bool:
    if isinstance(exc, (asyncio.TimeoutError, httpx.TimeoutException, httpx.TransportError)):
        return True
    status = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)
    return status == 429 or (isinstance(status, int) and status >= 500)


async def call(provider: str, kind: str, fn: Callable[[], Awaitable[T]]) -> T:
    for attempt in range(len(BACKOFF) + 1):
        start = time.perf_counter()
        try:
            result = await asyncio.wait_for(fn(), TIMEOUTS[kind])
            log.info("model_call", provider=provider, kind=kind, attempt=attempt,
                     latency_ms=round((time.perf_counter() - start) * 1000))
            return result
        except Exception as exc:  # noqa: BLE001 — classified below
            log.warning("model_call_failed", provider=provider, kind=kind, attempt=attempt,
                        error=type(exc).__name__)
            if attempt < len(BACKOFF) and _transient(exc):
                await asyncio.sleep(BACKOFF[attempt])
                continue
            raise AppError("ai_unavailable", 503, "AI abhi available nahi hai. Likh kar ya manually bharein.") from exc
    raise AssertionError("unreachable")
