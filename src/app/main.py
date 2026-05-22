import logging
import sys
import time
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
import fastapi
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from fastapi.middleware.gzip import GZipMiddleware
from app.config import config
from app.api.error_handlers import registrar_manejadores_error
from app.api.v1.middlewares.rate_limiter import AsyncRateLimiter
from app.api.v1.middlewares.security import SecurityHeadersMiddleware, RequestTracingMiddleware
from app.api.v1.middlewares.idempotency import IdempotencyMiddleware
from app.api.v1.middlewares.auditoria import AuditoriaMiddleware
from app.api.v1.middlewares.body_limit import BodySizeLimitMiddleware
from app.api.v1.middlewares.lowercase_path import LowerCasePathMiddleware
from app.api.v1.middlewares.tenant import TenantResolutionMiddleware
from app.api.v1.routers.auth import auth, usuarios, roles, auditoria, api_keys
from app.api.v1.routers.movilidad import cuentas as mov_cuentas
from app.api.v1.routers.movilidad import traslados as mov_traslados
from app.api.v1.routers.movilidad import radicaciones as mov_radicaciones
from app.api.v1.routers.movilidad import novedades as mov_novedades
from app.api.v1.routers.movilidad import reportes as mov_reportes
from app.api.v1.routers.movilidad import catalogos as mov_catalogos
from app.api.v1.routers.nunc import sesiones as nunc_sesiones
from app.api.v1.routers.parqueadero import vehiculos as parq_vehiculos
from app.api.v1.routers.parqueadero import inspecciones as parq_inspecciones
from app.api.v1.routers.parqueadero import alertas as parq_alertas
from app.api.v1.routers.parqueadero import inventarios as parq_inventarios
from app.infrastructure.persistence.database import init_db

_IS_DEV = config.APP_ENV == "development"

_COLORES = {
    "DEBUG":    "\033[34m DEBUG\033[0m",
    "INFO":     "\033[32m INFO \033[0m",
    "WARNING":  "\033[33m WARN \033[0m",
    "ERROR":    "\033[31m ERROR\033[0m",
    "CRITICAL": "\033[35m CRIT \033[0m",
}

_SILENCIAR = ["sqlalchemy.engine", "sqlalchemy.pool", "watchfiles", "asyncio"]


class _ColorFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        partes = record.name.split(".")
        record.name_corto = ".".join(partes[-2:]) if len(partes) > 2 else record.name
        record.nivel_color = _COLORES.get(record.levelname, record.levelname)
        return super().format(record)


if _IS_DEV:
    _fmt = _ColorFormatter(
        fmt="\033[90m%(asctime)s\033[0m |%(nivel_color)s| \033[36m%(name_corto)-28s\033[0m| %(message)s",
        datefmt="%H:%M:%S",
    )
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(_fmt)
    logging.root.handlers = [_handler]
    logging.root.setLevel(logging.INFO)
    for _m in _SILENCIAR:
        logging.getLogger(_m).setLevel(logging.WARNING)
else:
    import json as _json

    _CAMPOS_SENSIBLES = frozenset({"password", "nueva_password", "password_actual", "token", "access_token", "refresh_token", "key", "secret", "authorization"})

    def _sanitizar_extra(extra: dict) -> dict:
        return {
            k: "***" if k.lower() in _CAMPOS_SENSIBLES else v
            for k, v in extra.items()
        }

    class _JsonFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            base = {
                "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
            extra = {k: v for k, v in record.__dict__.items()
                     if k not in logging.LogRecord.__dict__ and not k.startswith("_")}
            base.update(_sanitizar_extra(extra))
            return _json.dumps(base, default=str, ensure_ascii=False)

    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(_JsonFormatter())
    logging.root.handlers = [_handler]
    logging.root.setLevel(logging.INFO)
    for _m in _SILENCIAR:
        logging.getLogger(_m).setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def _print_banner() -> None:
    py = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    fa = fastapi.__version__
    env = config.APP_ENV.upper()
    name = config.APP_NAME.upper()
    lineas = [f" {name} v1.0.0", f" Environment : {env}", f" Python      : {py}", f" FastAPI     : {fa}"]
    ancho = max(len(l) for l in lineas) + 2
    borde = "-" * ancho
    try:
        print(f"\n+{borde}+")
        for l in lineas:
            print(f"| {l:<{ancho - 1}}|")
        print(f"+{borde}+\n")
    except UnicodeEncodeError:
        print(f"\n{name} v1.0.0 | {env} | Python {py} | FastAPI {fa}\n")


@asynccontextmanager
async def lifespan(app: FastAPI):
    startup_start = time.perf_counter()

    if _IS_DEV:
        _print_banner()

    logger.info(f"Iniciando {config.APP_NAME} [{config.APP_ENV}] v1.0.0")
    config.validar_produccion()

    try:
        t = time.perf_counter()
        await init_db()
        logger.info(f"PostgreSQL (Supabase) ........... OK ({(time.perf_counter() - t) * 1000:.0f}ms)")
    except Exception as exc:
        logger.error(f"PostgreSQL ..................... FALLO — {exc}")

    redis_client = None
    try:
        from app.infrastructure.cache.redis_service import get_redis_client
        t = time.perf_counter()
        redis_client = get_redis_client()
        await redis_client.ping()
        logger.info(f"Redis .......................... OK ({(time.perf_counter() - t) * 1000:.0f}ms)")
    except Exception as exc:
        logger.warning(f"Redis .......................... FALLO — {exc}")

    if config.APP_ENV == "production" and "*" in config.ALLOWED_HOSTS:
        logger.critical("SEGURIDAD: ALLOWED_HOSTS contiene '*' en producción.")

    total_ms = (time.perf_counter() - startup_start) * 1000
    logger.info(f"Servidor listo — startup en {total_ms:.0f}ms")

    yield

    logger.info("Cerrando aplicación...")
    try:
        from app.infrastructure.persistence.database import engine
        await engine.dispose()
        logger.info("PostgreSQL pool cerrado")
    except Exception as exc:
        logger.warning(f"Error cerrando PostgreSQL pool — {exc}")
    try:
        from app.infrastructure.cache.redis_service import close_redis_pool
        await close_redis_pool()
        logger.info("Redis pool cerrado")
    except Exception as exc:
        logger.warning(f"Error cerrando Redis — {exc}")


def crear_app() -> FastAPI:
    _limiter_global = Depends(AsyncRateLimiter(times=config.RATE_LIMIT_PER_MINUTE, seconds=60))

    _tags = [
        {"name": "Auth",                     "description": "Login, logout, refresh de tokens JWT y verificación de email."},
        {"name": "Usuarios",                  "description": "Gestión de usuarios: crear, listar, activar/desactivar y cambiar contraseña."},
        {"name": "Roles & Permisos",          "description": "Creación de roles, asignación de permisos y vinculación a usuarios (RBAC)."},
        {"name": "API Keys",                  "description": "Generación y revocación de API Keys para integración service-to-service."},
        {"name": "Auditoria",                 "description": "Historial inmutable de operaciones de escritura con firma criptográfica."},
        {"name": "Movilidad — Cuentas",       "description": "Cuentas asociadas a una placa vehicular. Punto de entrada para traslados y radicaciones. Incluye consulta pública por placa."},
        {"name": "Movilidad — Traslados",     "description": "Traslado de vehículo entre organismos. Estados: pendiente, aprobado, en_transito, recibido, completado, devuelto. Genera PDF de remisión."},
        {"name": "Movilidad — Radicaciones",  "description": "Radicación ante el organismo destino tras traslado aprobado. Estados: pendiente, en_revision, aprobada, radicada, completada, devuelta."},
        {"name": "Movilidad — Novedades",     "description": "Registro y resolución de novedades sobre traslados y radicaciones."},
        {"name": "Movilidad — Reportes",      "description": "Dashboard con contadores por estado y reportes filtrables por fecha y organismo."},
        {"name": "Movilidad — Catálogos",     "description": "Catálogos compartidos: organismos de tránsito y empresas transportadoras."},
        {"name": "Parqueadero — Vehículos",   "description": "Vehículos del parqueadero con seguimiento de documentos (SOAT, tecnomecánica)."},
        {"name": "Parqueadero — Inspecciones","description": "Inspecciones de ingreso y salida de vehículos."},
        {"name": "Parqueadero — Inventarios", "description": "Insumos, stock, rangos de numeración, movimientos y cierres de inventario."},
        {"name": "Parqueadero — Alertas",     "description": "Alertas de vencimiento de SOAT, tecnomecánica y licencias de operadores."},
        {"name": "NUNC",                      "description": "Gestión de sesiones del módulo NUNC."},
        {"name": "Sistema",                   "description": "Health checks y estado de la API."},
    ]

    app = FastAPI(
        title="API Movilidad",
        version="0.3.0",
        description=(
            "API para la gestión de movilidad vehicular y parqueadero. "
            "Módulos: traslados, radicaciones, cuentas, inventarios, reportes y auditoría.\n\n"
            "La mayoría de endpoints requieren autenticación con Bearer token JWT. "
            "Obtén el token en `POST /api/v1/auth/login`.\n\n"
            "Los listados usan paginación por cursor: pasa `siguiente_cursor` del response "
            "como parámetro `cursor` en la siguiente petición."
        ),
        openapi_tags=_tags,
        docs_url="/docs" if config.APP_ENV != "production" else None,
        redoc_url=None,
        openapi_url="/openapi.json" if config.APP_ENV != "production" else None,
        lifespan=lifespan,
    )

    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(LowerCasePathMiddleware)
    app.add_middleware(BodySizeLimitMiddleware)
    app.add_middleware(TenantResolutionMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestTracingMiddleware)
    app.add_middleware(AuditoriaMiddleware)
    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Correlation-ID", "Idempotency-Key"],
    )
    if config.APP_ENV == "production":
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=config.ALLOWED_HOSTS)

    registrar_manejadores_error(app)

    # Prometheus metrics en /metrics (ASGI puro, sin overhead de BaseHTTPMiddleware)
    try:
        from app.infrastructure.observability import iniciar_metrics
        iniciar_metrics(app)
    except ImportError:
        logger.warning("prometheus-client no instalado — /metrics deshabilitado")

    prefix = config.API_V1_PREFIX
    app.include_router(auth.router,     prefix=f"{prefix}/auth",      tags=["Auth"],             dependencies=[_limiter_global])
    app.include_router(usuarios.router, prefix=f"{prefix}/usuarios",  tags=["Usuarios"],         dependencies=[_limiter_global])
    app.include_router(roles.router,    prefix=f"{prefix}/roles",     tags=["Roles & Permisos"], dependencies=[_limiter_global])
    app.include_router(auditoria.router,prefix=f"{prefix}/auditoria", tags=["Auditoria"],        dependencies=[_limiter_global])
    app.include_router(api_keys.router, prefix=f"{prefix}/api-keys",  tags=["API Keys"],         dependencies=[_limiter_global])

    # Movilidad
    app.include_router(mov_cuentas.router,     prefix=f"{prefix}/movilidad/cuentas",     tags=["Movilidad — Cuentas"],     dependencies=[_limiter_global])
    app.include_router(mov_traslados.router,   prefix=f"{prefix}/movilidad/traslados",   tags=["Movilidad — Traslados"],   dependencies=[_limiter_global])
    app.include_router(mov_radicaciones.router,prefix=f"{prefix}/movilidad/radicaciones",tags=["Movilidad — Radicaciones"],dependencies=[_limiter_global])
    app.include_router(mov_novedades.router,   prefix=f"{prefix}/movilidad/novedades",   tags=["Movilidad — Novedades"],   dependencies=[_limiter_global])
    app.include_router(mov_reportes.router,   prefix=f"{prefix}/movilidad",             tags=["Movilidad — Reportes"],    dependencies=[_limiter_global])
    app.include_router(mov_catalogos.router,  prefix=f"{prefix}/movilidad",             tags=["Movilidad — Catálogos"],   dependencies=[_limiter_global])

    # NUNC
    app.include_router(nunc_sesiones.router, prefix=f"{prefix}/nunc", tags=["NUNC"], dependencies=[_limiter_global])

    # Parqueadero
    app.include_router(parq_vehiculos.router,    prefix=f"{prefix}/parqueadero/vehiculos",    tags=["Parqueadero — Vehículos"],    dependencies=[_limiter_global])
    app.include_router(parq_inspecciones.router, prefix=f"{prefix}/parqueadero/inspecciones", tags=["Parqueadero — Inspecciones"], dependencies=[_limiter_global])
    app.include_router(parq_alertas.router,      prefix=f"{prefix}/parqueadero",              tags=["Parqueadero — Alertas"],      dependencies=[_limiter_global])
    app.include_router(parq_inventarios.router,  prefix=f"{prefix}/parqueadero",              tags=["Parqueadero — Inventarios"],  dependencies=[_limiter_global])

    if config.APP_ENV != "production":
        from fastapi.openapi.docs import get_redoc_html

        @app.get("/redoc", include_in_schema=False)
        async def redoc_html():
            return get_redoc_html(
                openapi_url="/openapi.json",
                title=config.APP_NAME,
                redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@2.1.3/bundles/redoc.standalone.js",
            )

    @app.get("/", include_in_schema=False)
    async def root():
        return {"mensaje": "Página principal"}

    @app.get("/health", tags=["Sistema"], summary="Estado de la API")
    async def health():
        """Verifica que la API está corriendo. No requiere autenticación."""
        if config.APP_ENV == "production":
            return {"status": "ok"}
        return {"status": "ok", "env": config.APP_ENV, "version": "0.3.0"}

    @app.get("/ready", tags=["Sistema"], summary="Readiness check")
    async def ready():
        from sqlalchemy import text
        from fastapi.responses import JSONResponse
        from app.infrastructure.persistence.database import engine
        checks = {}
        ok = True
        try:
            t = time.perf_counter()
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            checks["postgresql"] = {"status": "ok", "latency_ms": round((time.perf_counter() - t) * 1000)}
        except Exception as exc:
            detail = str(exc) if config.APP_ENV != "production" else "connection error"
            checks["postgresql"] = {"status": "error", "detail": detail}
            ok = False
        try:
            from app.infrastructure.cache.redis_service import get_redis_client
            t = time.perf_counter()
            await get_redis_client().ping()
            checks["redis"] = {"status": "ok", "latency_ms": round((time.perf_counter() - t) * 1000)}
        except Exception as exc:
            detail = str(exc) if config.APP_ENV != "production" else "connection error"
            checks["redis"] = {"status": "error", "detail": detail}
        if not ok:
            return JSONResponse(status_code=503, content={"status": "not ready", "checks": checks})
        return {"status": "ready", "checks": checks}

    return app


app = crear_app()
