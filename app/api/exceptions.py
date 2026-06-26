from __future__ import annotations

import logging
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import RedirectResponse

from app.utils.logging import log_exception

logger = logging.getLogger(__name__)


async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    log_exception("database", f"Unhandled database error on {request.url.path}", exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "Database temporarily unavailable. Please try again."},
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse | RedirectResponse:
    if isinstance(exc, SQLAlchemyError):
        return await sqlalchemy_exception_handler(request, exc)

    log_exception("app", f"Unhandled error on {request.url.path}", exc)

    accept = request.headers.get("accept", "")
    if "text/html" in accept and request.url.path.startswith("/dashboard"):
        return RedirectResponse(url="/dashboard?error=server", status_code=303)

    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred."},
    )
