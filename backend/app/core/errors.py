"""Domain errors. Services raise these; FastAPI maps them to HTTP in one handler."""

from __future__ import annotations

import logging
from collections.abc import Mapping

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Typed domain failure. Not a FastAPI HTTPException — workers can catch this."""

    status_code = 400

    def __init__(self, detail: str, *, status_code: int | None = None) -> None:
        self.detail = detail
        if status_code is not None:
            self.status_code = status_code
        super().__init__(detail)


class BadRequestError(AppError):
    status_code = 400


class UnauthorizedError(AppError):
    status_code = 401


class PaymentRequiredError(AppError):
    status_code = 402


class ForbiddenError(AppError):
    status_code = 403


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    status_code = 409


class GoneError(AppError):
    status_code = 410


class PayloadTooLargeError(AppError):
    status_code = 413


class UnprocessableError(AppError):
    status_code = 422


class UnavailableError(AppError):
    status_code = 503


def register_error_handlers(app: FastAPI) -> None:
    """Map all HTTP failures to the stable `{error: ...}` API envelope."""
    @app.exception_handler(AppError)
    async def _app_error(_request: Request, exc: AppError) -> JSONResponse:
        return api_error_response(
            exc.status_code,
            _app_error_code(exc),
            exc.detail,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        status_code = exc.status_code
        detail = exc.detail
        message = (
            detail
            if isinstance(detail, str) and status_code < 500
            else _default_error_message(status_code)
        )
        return api_error_response(
            status_code,
            _http_error_code(status_code),
            message,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        issues = [
            {
                "location": [part.value if hasattr(part, "value") else part for part in item.get("loc", ())],
                "code": str(item.get("type", "invalid")),
            }
            for item in exc.errors()
        ]
        return api_error_response(
            422,
            "request.validation",
            "Request validation failed",
            details={"issues": issues},
        )

    @app.exception_handler(Exception)
    async def _unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "unhandled API error path=%s method=%s error_type=%s",
            request.url.path,
            request.method,
            type(exc).__name__,
        )
        return api_error_response(500, "internal.server_error", "An internal error occurred")


def api_error_response(
    status_code: int,
    code: str,
    message: str,
    *,
    details: dict | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    error: dict[str, object] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return JSONResponse(
        status_code=status_code,
        content={"error": error},
        headers=headers,
    )


def _app_error_code(exc: AppError) -> str:
    return {
        BadRequestError: "request.bad_request",
        UnauthorizedError: "auth.unauthorized",
        PaymentRequiredError: "billing.payment_required",
        ForbiddenError: "auth.forbidden",
        NotFoundError: "resource.not_found",
        ConflictError: "resource.conflict",
        GoneError: "resource.gone",
        PayloadTooLargeError: "request.payload_too_large",
        UnprocessableError: "request.unprocessable",
        UnavailableError: "service.unavailable",
    }.get(type(exc), "request.failed")


def _http_error_code(status_code: int) -> str:
    return {
        400: "request.bad_request",
        401: "auth.unauthorized",
        403: "auth.forbidden",
        404: "resource.not_found",
        409: "resource.conflict",
        410: "resource.gone",
        413: "request.payload_too_large",
        422: "request.invalid",
        429: "rate_limit.exceeded",
        500: "internal.server_error",
        503: "service.unavailable",
    }.get(status_code, "request.failed")


def _default_error_message(status_code: int) -> str:
    return {
        401: "Authentication required",
        403: "Access denied",
        404: "Resource not found",
        429: "Too many requests",
        503: "Service temporarily unavailable",
    }.get(status_code, "An internal error occurred" if status_code >= 500 else "Request failed")
