import traceback
from collections.abc import Mapping, Sequence
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from pii_guard.observability.logging import get_logger

logger = get_logger("pii_guard.errors")


def _is_json_invalid(exc: RequestValidationError) -> bool:
    return any(err.get("type") == "json_invalid" for err in exc.errors())


def _safe_detail(errors: Sequence[Any]) -> list[dict[str, Any]]:
    detail: list[dict[str, Any]] = []
    for err in errors:
        if not isinstance(err, Mapping):
            continue
        detail.append(
            {
                "loc": list(err.get("loc", [])),
                "msg": err.get("msg", ""),
                "type": err.get("type", ""),
            }
        )
    return detail


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        if _is_json_invalid(exc):
            return JSONResponse(status_code=400, content={"error": "invalid_json"})
        return JSONResponse(
            status_code=422,
            content={"error": "invalid_request", "detail": _safe_detail(exc.errors())},
        )

    @app.exception_handler(Exception)
    async def _internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
        tb = traceback.extract_tb(exc.__traceback__)
        frame = tb[-1] if tb else None
        location = f"{frame.filename}:{frame.lineno}" if frame else "unknown"
        logger.error(
            "unhandled_exception",
            exc_type=type(exc).__name__,
            location=location,
        )
        request_id = structlog.contextvars.get_contextvars().get("request_id", "")
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "request_id": request_id},
        )
