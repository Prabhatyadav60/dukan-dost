from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    def __init__(self, code: str, status: int, message: str, details: dict[str, Any] | None = None,
                 headers: dict[str, str] | None = None):
        self.code, self.status, self.message = code, status, message
        self.details = details or {}
        self.headers = headers


def _envelope(request: Request, code: str, message: str, details: dict | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or {},
                      "request_id": getattr(request.state, "request_id", None)}}


def install(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        return JSONResponse(_envelope(request, exc.code, exc.message, exc.details), exc.status,
                            headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        fields = [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]
        return JSONResponse(_envelope(request, "validation_error", "Request is invalid.", {"fields": fields}), 422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        code = "not_found" if exc.status_code == 404 else "http_error"
        return JSONResponse(_envelope(request, code, str(exc.detail)), exc.status_code)


def not_found() -> AppError:
    return AppError("not_found", 404, "Not found.")
