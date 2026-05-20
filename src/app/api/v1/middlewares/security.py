import time
from app.infrastructure.identity import uuid7
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


_DOCS_PREFIJOS = ("/docs", "/redoc", "/openapi.json")

_CSP_DOCS = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https://fastapi.tiangolo.com; "
    "connect-src 'self'; "
    "frame-ancestors 'none'"
)
_CSP_API = "default-src 'none'; frame-ancestors 'none'"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"

        es_docs = request.url.path.startswith(_DOCS_PREFIJOS)
        response.headers["Content-Security-Policy"] = _CSP_DOCS if es_docs else _CSP_API

        if "server" in response.headers:
            del response.headers["server"]
        return response


class RequestTracingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid7()))
        request.state.correlation_id = correlation_id
        start = time.perf_counter()

        response = await call_next(request)

        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"

        try:
            from opentelemetry import trace as otel_trace
            span = otel_trace.get_current_span()
            if span.is_recording():
                ctx = span.get_span_context()
                trace_id = format(ctx.trace_id, "032x")
                response.headers["X-Trace-ID"] = trace_id
        except Exception:
            pass

        logger.info(
            "request",
            extra={
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "ms": round(elapsed_ms, 2),
            },
        )
        return response
