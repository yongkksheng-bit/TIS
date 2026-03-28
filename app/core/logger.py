"""Structured logging via structlog — outputs JSON for ELK/Aliyun Log compatibility."""
import logging
import sys
import time
import uuid
from typing import Optional

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# ── structlog configuration ────────────────────────────────────────────────


def add_app_context(logger, method_name, event_dict):
    """Add global app context to every log event."""
    event_dict["app"] = "tis"
    event_dict["version"] = "1.0.0"
    return event_dict


def rename_event_key(logger, method_name, event_dict):
    """Rename 'event' key to 'message' for standard JSON field name."""
    if "event" in event_dict:
        event_dict["message"] = event_dict.pop("event")
    return event_dict


structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        rename_event_key,
        add_app_context,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)


def get_logger(name: Optional[str] = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


# ── Request logging middleware ──────────────────────────────────────────────


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that:
    - Assigns a unique request_id to every incoming request
    - Logs request start with method, path, request_id
    - Logs request completion with status_code and duration_ms
    - Attaches request_id to response headers for tracing
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())[:8]

        # Bind request_id to structlog context for this request
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        log = get_logger("http")
        log.info(
            "request_started",
            method=request.method,
            path=request.url.path,
            client=request.client.host if request.client else None,
        )

        start_time = time.perf_counter()
        response: Response = await call_next(request)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Attach request_id to response headers so clients can trace
        response.headers["X-Request-ID"] = request_id

        log.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        return response