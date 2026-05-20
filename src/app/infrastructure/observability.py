"""
Observabilidad: structured logging (prod) + OpenTelemetry (trazas distribuidas).

- Desarrollo : logging coloreado legible + OTel opcional
- Producción : JSON válido con python-json-logger + OTel con exporter OTLP
"""
import logging
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

_SILENCIAR = [
    "sqlalchemy.engine",
    "sqlalchemy.pool",
    "watchfiles",
    "asyncio",
    "opentelemetry",
]

_COLORES = {
    "DEBUG":    "\033[34m DEBUG\033[0m",
    "INFO":     "\033[32m INFO \033[0m",
    "WARNING":  "\033[33m WARN \033[0m",
    "ERROR":    "\033[31m ERROR\033[0m",
    "CRITICAL": "\033[35m CRIT \033[0m",
}


# ── Filtro que inyecta trace_id/span_id desde OTel context ───────────────────

class _OtelContextFilter(logging.Filter):
    """Agrega trace_id y span_id al LogRecord si hay un span activo."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            from opentelemetry import trace
            span = trace.get_current_span()
            if span.is_recording():
                ctx = span.get_span_context()
                record.trace_id = format(ctx.trace_id, "032x")
                record.span_id = format(ctx.span_id, "016x")
            else:
                record.trace_id = ""
                record.span_id = ""
        except Exception:
            record.trace_id = ""
            record.span_id = ""
        return True


# ── Formatter de desarrollo (colores) ────────────────────────────────────────

class _ColorFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        partes = record.name.split(".")
        record.name_corto = ".".join(partes[-2:]) if len(partes) > 2 else record.name
        record.nivel_color = _COLORES.get(record.levelname, record.levelname)
        return super().format(record)


# ── Configuración de logging ──────────────────────────────────────────────────

def configurar_logging(es_dev: bool) -> None:
    """
    Dev  → formatter coloreado legible por humanos.
    Prod → JsonFormatter (python-json-logger): JSON válido, extra fields incluidos,
           trace_id/span_id inyectados automáticamente desde OTel context.
    """
    otel_filter = _OtelContextFilter()
    root = logging.getLogger()
    root.handlers.clear()

    if es_dev:
        fmt = _ColorFormatter(
            fmt="\033[90m%(asctime)s\033[0m |%(nivel_color)s| \033[36m%(name_corto)-28s\033[0m| %(message)s",
            datefmt="%H:%M:%S",
        )
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(fmt)
        handler.addFilter(otel_filter)
        root.addHandler(handler)
        root.setLevel(logging.INFO)
        for modulo in _SILENCIAR:
            logging.getLogger(modulo).setLevel(logging.WARNING)
    else:
        from pythonjsonlogger.json import JsonFormatter

        fmt_json = JsonFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s %(trace_id)s %(span_id)s",
            rename_fields={
                "asctime": "timestamp",
                "levelname": "level",
                "name": "logger",
            },
        )
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(fmt_json)
        handler.addFilter(otel_filter)
        root.addHandler(handler)
        root.setLevel(logging.INFO)
        for modulo in _SILENCIAR:
            logging.getLogger(modulo).setLevel(logging.WARNING)


# ── Setup OpenTelemetry ───────────────────────────────────────────────────────

def iniciar_otel(app: "FastAPI", otlp_endpoint: str, service_name: str) -> None:
    """
    Configura OpenTelemetry con instrumentación automática para:
      - FastAPI  (cada request = un span raíz)
      - SQLAlchemy (cada query = span hijo)
      - Redis (cada comando = span hijo)

    Exporter:
      - Si otlp_endpoint está configurado → OTLPSpanExporter (gRPC) hacia el collector
      - Si no → ConsoleSpanExporter (útil para debug local)
    """
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.semconv.resource import ResourceAttributes
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from app.infrastructure.persistence.database import engine

    resource = Resource({ResourceAttributes.SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)

    if otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    else:
        exporter = ConsoleSpanExporter()

    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
    SQLAlchemyInstrumentor().instrument(
        engine=engine.sync_engine,
        tracer_provider=provider,
    )
    RedisInstrumentor().instrument(tracer_provider=provider)

    logging.getLogger(__name__).info(
        "OpenTelemetry activo",
        extra={"exporter": otlp_endpoint or "console", "service": service_name},
    )


# ── Setup Prometheus metrics ──────────────────────────────────────────────────

def iniciar_metrics(app: "FastAPI") -> None:
    """
    Instrumentación Prometheus sin BaseHTTPMiddleware.

    Registry aislado (sin GC, platform ni process metrics de Python).
    Métricas expuestas en GET /metrics:
      - http_requests_total          counter{method, path, status}
      - http_request_duration_seconds histograma p50/p95/p99
      - http_requests_inprogress     gauge de requests activos
    """
    import time
    from prometheus_client import (
        Counter, Histogram, Gauge,
        CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST,
    )
    from starlette.types import ASGIApp, Receive, Scope, Send
    from starlette.requests import Request
    from starlette.responses import Response

    # Registry propio — excluye los colectores default de Python (GC, platform, process)
    _registry = CollectorRegistry()

    # Paths y extensiones que no vale la pena medir
    _IGNORAR = {
        "/metrics", "/health", "/ready",
        "/docs", "/redoc", "/openapi.json",
        "/favicon.ico", "/robots.txt",
    }
    _IGNORAR_EXT = {".ico", ".png", ".jpg", ".css", ".js", ".map", ".woff", ".woff2"}

    requests_total = Counter(
        "http_requests_total",
        "Total de HTTP requests",
        ["method", "path", "status"],
        registry=_registry,
    )
    duration = Histogram(
        "http_request_duration_seconds",
        "Duración de HTTP requests en segundos",
        ["method", "path"],
        buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
        registry=_registry,
    )
    inprogress = Gauge(
        "http_requests_inprogress",
        "Requests HTTP activos",
        ["method"],
        registry=_registry,
    )

    class MetricsMiddleware:
        """ASGI middleware puro — no hereda de BaseHTTPMiddleware."""

        def __init__(self, app: ASGIApp) -> None:
            self.app = app

        async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
            if scope["type"] != "http":
                await self.app(scope, receive, send)
                return

            # Normalizar slashes dobles (//health → /health)
            raw_path = scope.get("path", "")
            path = "/" + raw_path.lstrip("/") if raw_path else "/"

            # Ignorar rutas de infraestructura y assets estáticos
            if path in _IGNORAR:
                await self.app(scope, receive, send)
                return
            ext = path.rsplit(".", 1)[-1] if "." in path.split("/")[-1] else ""
            if f".{ext}" in _IGNORAR_EXT:
                await self.app(scope, receive, send)
                return

            method = scope.get("method", "")
            start = time.perf_counter()
            status_code = 500

            inprogress.labels(method=method).inc()

            async def send_wrapper(message: dict) -> None:
                nonlocal status_code
                if message["type"] == "http.response.start":
                    status_code = message["status"]
                await send(message)

            try:
                await self.app(scope, receive, send_wrapper)
            finally:
                elapsed = time.perf_counter() - start
                requests_total.labels(method=method, path=path, status=str(status_code)).inc()
                duration.labels(method=method, path=path).observe(elapsed)
                inprogress.labels(method=method).dec()

    app.add_middleware(MetricsMiddleware)

    async def _metrics_view(request: Request) -> Response:
        from app.config import config as _cfg
        if _cfg.METRICS_SECRET:
            token = request.query_params.get("token", "")
            if token != _cfg.METRICS_SECRET:
                return Response(status_code=403, content="Forbidden")
        return Response(
            content=generate_latest(_registry),
            media_type=CONTENT_TYPE_LATEST,
        )

    app.add_route("/metrics", _metrics_view, methods=["GET"], include_in_schema=False)

    logging.getLogger(__name__).info("Prometheus metrics activas en /metrics")
