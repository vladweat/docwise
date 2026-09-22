"""Domain errors. Services raise these; FastAPI maps them to HTTP in one handler."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


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
    """Map `AppError` subclasses to JSON `{detail}` responses."""
    @app.exception_handler(AppError)
    async def _app_error(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
