import os

import sentry_sdk
from fastapi import Request
from fastapi.responses import JSONResponse

from utils.logger import get_logger


logger = get_logger("solo.errors")


async def http_exception_handler(request: Request, exc):
    logger.warning(
        "HTTP exception",
        extra={
            "path": request.url.path,
            "status": exc.status_code,
            "detail": str(exc.detail),
        },
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": str(exc.detail)},
        headers=getattr(exc, "headers", None),
    )


async def general_exception_handler(request: Request, exc):
    logger.error(
        "Unhandled exception",
        extra={
            "path": request.url.path,
            "error": str(exc),
            "type": type(exc).__name__,
        },
    )
    if os.getenv("SENTRY_DSN"):
        sentry_sdk.capture_exception(exc)

    if os.getenv("ENV") == "production":
        message = "Something went wrong. Our team has been notified."
    else:
        message = str(exc)

    return JSONResponse(status_code=500, content={"error": message})
