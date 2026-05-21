import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.domain.exceptions import (
    EntidadNoEncontrada, EmailYaRegistrado, CredencialesInvalidas, CuentaBloqueada,
    UsuarioInactivo, VerificacionPendiente, TokenInvalido, TokenExpirado, TokenRevocado,
    PermisoDenegado, ReglaDeNegocioViolada, FirmaInvalida,
    ApiKeyInvalida, RolNoEncontrado, PermisoNoEncontrado,
)

logger = logging.getLogger(__name__)


def _campo(loc: tuple) -> str:
    partes = [str(x) for x in loc]
    if partes and partes[0] in ("body", "query", "path", "header", "cookie"):
        partes = partes[1:]
    return ".".join(partes) if partes else "request"


def _mensaje(tipo: str, msg: str, ctx: dict) -> str:
    if tipo == "missing":
        return "Campo requerido"
    if tipo == "string_too_short":
        return f"Mínimo {ctx.get('min_length', '?')} caracteres"
    if tipo == "string_too_long":
        return f"Máximo {ctx.get('max_length', '?')} caracteres"
    if tipo == "string_pattern_mismatch":
        return "Formato inválido"
    if tipo in ("string_type", "string_unicode"):
        return "Debe ser texto"
    if tipo in ("int_type", "int_parsing"):
        return "Debe ser un número entero"
    if tipo in ("float_type", "float_parsing"):
        return "Debe ser un número"
    if tipo == "bool_type":
        return "Debe ser verdadero o falso"
    if tipo == "enum":
        return f"Valor inválido. Opciones: {ctx.get('expected', '')}"
    if tipo == "json_invalid":
        return "El cuerpo de la petición debe ser JSON válido"
    if tipo in ("datetime_type", "datetime_parsing"):
        return "Fecha inválida. Use ISO 8601 (ej: 2026-12-31T23:59:59Z)"
    if tipo in ("uuid_type", "uuid_parsing"):
        return "Debe ser un UUID válido"
    if tipo in ("too_short", "list_type"):
        return f"Mínimo {ctx.get('min_length', '?')} elementos"
    if tipo == "too_long":
        return f"Máximo {ctx.get('max_length', '?')} elementos"
    if tipo == "value_error":
        return msg.removeprefix("Value error, ")
    return msg


def registrar_manejadores_error(app: FastAPI) -> None:

    @app.exception_handler(StarletteHTTPException)
    async def http_exception(request: Request, exc: StarletteHTTPException):
        # Solo redirigir al root desde rutas no-API (ej: navegador en ruta desconocida)
        if exc.status_code == 404 and not request.url.path.startswith("/api/"):
            return RedirectResponse(url="/", status_code=302)
        return JSONResponse(status_code=exc.status_code, content={"detalle": exc.detail})

    @app.exception_handler(RequestValidationError)
    async def validacion(request: Request, exc: RequestValidationError):
        errores = [
            {
                "campo": _campo(e["loc"]),
                "mensaje": _mensaje(e["type"], e["msg"], e.get("ctx") or {}),
            }
            for e in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={"detalle": "Error de validación", "errores": errores},
        )

    @app.exception_handler(EntidadNoEncontrada)
    async def no_encontrada(request: Request, exc: EntidadNoEncontrada):
        return JSONResponse(status_code=404, content={"detalle": str(exc)})

    @app.exception_handler(EmailYaRegistrado)
    async def email_duplicado(request: Request, exc: EmailYaRegistrado):
        return JSONResponse(status_code=409, content={"detalle": str(exc)})

    @app.exception_handler(CredencialesInvalidas)
    async def credenciales(request: Request, exc: CredencialesInvalidas):
        return JSONResponse(status_code=401, content={"detalle": "Credenciales inválidas"})

    @app.exception_handler(CuentaBloqueada)
    async def cuenta_bloqueada(request: Request, exc: CuentaBloqueada):
        minutos = exc.segundos_restantes // 60
        segundos = exc.segundos_restantes % 60
        if minutos > 0:
            tiempo = f"{minutos} min {segundos}s" if segundos else f"{minutos} min"
        else:
            tiempo = f"{exc.segundos_restantes}s"
        return JSONResponse(
            status_code=429,
            content={"detalle": f"Cuenta bloqueada por múltiples intentos fallidos. Intentá de nuevo en {tiempo}."},
            headers={"Retry-After": str(exc.segundos_restantes)},
        )

    @app.exception_handler(UsuarioInactivo)
    async def inactivo(request: Request, exc: UsuarioInactivo):
        return JSONResponse(status_code=403, content={"detalle": str(exc)})

    @app.exception_handler(VerificacionPendiente)
    async def verificacion_pendiente(request: Request, exc: VerificacionPendiente):
        return JSONResponse(
            status_code=403,
            content={
                "detalle": str(exc),
                "codigo": "EMAIL_NO_VERIFICADO",
            },
        )

    @app.exception_handler(TokenInvalido)
    async def token_inv(request: Request, exc: TokenInvalido):
        return JSONResponse(status_code=401, content={"detalle": "Token inválido"})

    @app.exception_handler(TokenExpirado)
    async def token_exp(request: Request, exc: TokenExpirado):
        return JSONResponse(
            status_code=401,
            content={"detalle": "Token expirado", "codigo": "TOKEN_EXPIRED"},
        )

    @app.exception_handler(TokenRevocado)
    async def token_rev(request: Request, exc: TokenRevocado):
        return JSONResponse(status_code=401, content={"detalle": "Sesión cerrada"})

    @app.exception_handler(PermisoDenegado)
    async def permiso(request: Request, exc: PermisoDenegado):
        return JSONResponse(status_code=403, content={"detalle": str(exc)})

    @app.exception_handler(ReglaDeNegocioViolada)
    async def regla(request: Request, exc: ReglaDeNegocioViolada):
        return JSONResponse(status_code=409, content={"detalle": str(exc)})

    @app.exception_handler(FirmaInvalida)
    async def firma(request: Request, exc: FirmaInvalida):
        return JSONResponse(status_code=401, content={"detalle": str(exc)})

    @app.exception_handler(ApiKeyInvalida)
    async def api_key(request: Request, exc: ApiKeyInvalida):
        return JSONResponse(status_code=401, content={"detalle": "API Key inválida o revocada"})

    @app.exception_handler(RolNoEncontrado)
    async def rol_nf(request: Request, exc: RolNoEncontrado):
        return JSONResponse(status_code=404, content={"detalle": str(exc)})

    @app.exception_handler(PermisoNoEncontrado)
    async def permiso_nf(request: Request, exc: PermisoNoEncontrado):
        return JSONResponse(status_code=404, content={"detalle": str(exc)})

    @app.exception_handler(Exception)
    async def generico(request: Request, exc: Exception):
        correlation_id = getattr(request.state, "correlation_id", "sin-id")
        logger.error(
            "Error inesperado",
            extra={"correlation_id": correlation_id},
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={"detalle": "Error interno", "correlacion": correlation_id},
        )
