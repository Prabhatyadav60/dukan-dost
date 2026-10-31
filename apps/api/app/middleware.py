import time
import uuid

import structlog
from fastapi import FastAPI, Request

log = structlog.get_logger()


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_id(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = rid
        start = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        log.info("request", request_id=rid, method=request.method, path=request.url.path,
                 status=response.status_code, latency_ms=round((time.perf_counter() - start) * 1000))
        return response
