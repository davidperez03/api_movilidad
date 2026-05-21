import asyncio
import json
import logging
import time
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import config
from app.domain.entities.auth.auditoria import (
    CategoriaEvento,
    NivelEvento,
    RegistroAuditoria,
    ResultadoAuditoria,
    TipoActor,
)

logger = logging.getLogger(__name__)

# ── Campos que nunca deben aparecer en el audit log ───────────────────────────
_CAMPOS_SENSIBLES: frozenset[str] = frozenset({
    "password", "nueva_password", "password_actual", "confirm_password",
    "token", "access_token", "refresh_token",
    "key", "secret", "key_hash", "hash_password",
    "authorization", "cookie", "cvv", "pin", "numero_tarjeta",
    "codigo", "code",
})

# ── Paths excluidos del audit (nunca auditamos rutas de infraestructura) ──────
_EXCLUIR_EXACTOS:  frozenset[str] = frozenset({"/health", "/ready", "/metrics", "/docs", "/redoc", "/openapi.json", "/"})
_EXCLUIR_PREFIJOS: tuple[str, ...] = ("/docs/", "/redoc/")

# ── GETs que SÍ se auditan aunque sean lecturas (datos sensibles) ─────────────
_GET_AUDITADOS: frozenset[str] = frozenset({
    "/api/v1/auditoria",
    "/api/v1/auditoria/estadisticas",
    "/api/v1/auditoria/exportar",
    "/api/v1/auditoria/verificar-integridad",
    "/api/v1/usuarios",
})

# ── Mapa: (METHOD, path_prefix_o_exacto) → (accion, categoria) ───────────────
_ACCIONES: dict[tuple[str, str], tuple[str, CategoriaEvento]] = {
    # Auth
    ("POST",   "/api/v1/auth/login"):                    ("auth.login",                CategoriaEvento.AUTH),
    ("POST",   "/api/v1/auth/logout"):                   ("auth.logout",               CategoriaEvento.AUTH),
    ("POST",   "/api/v1/auth/refresh"):                  ("auth.token_renovado",        CategoriaEvento.AUTH),
    ("POST",   "/api/v1/auth/verificar-email"):          ("auth.email_verificado",      CategoriaEvento.AUTH),
    ("POST",   "/api/v1/auth/reenviar-verificacion"):    ("auth.verificacion_reenviada",CategoriaEvento.AUTH),
    ("POST",   "/api/v1/auth/solicitar-reset-password"): ("auth.reset_solicitado",      CategoriaEvento.AUTH),
    ("POST",   "/api/v1/auth/reset-password"):           ("auth.password_cambiado",     CategoriaEvento.AUTH),
    # Usuarios
    ("POST",   "/api/v1/usuarios"):                      ("usuario.creado",             CategoriaEvento.USUARIO),
    ("PATCH",  "/api/v1/usuarios"):                      ("usuario.actualizado",        CategoriaEvento.USUARIO),
    ("PUT",    "/api/v1/usuarios"):                      ("usuario.actualizado",        CategoriaEvento.USUARIO),
    ("DELETE", "/api/v1/usuarios"):                      ("usuario.desactivado",        CategoriaEvento.USUARIO),
    ("GET",    "/api/v1/usuarios"):                      ("usuario.listado",            CategoriaEvento.DATOS),
    # Roles
    ("POST",   "/api/v1/roles"):                         ("rol.creado",                CategoriaEvento.ROL),
    ("DELETE", "/api/v1/roles"):                         ("rol.eliminado",             CategoriaEvento.ROL),
    ("POST",   "/api/v1/roles/asignar"):                 ("rol.asignado",              CategoriaEvento.ROL),
    ("DELETE", "/api/v1/roles/usuarios"):                ("rol.revocado",              CategoriaEvento.ROL),
    ("POST",   "/api/v1/roles/permisos"):                ("rol.permiso_asignado",      CategoriaEvento.ROL),
    # API Keys
    ("POST",   "/api/v1/api-keys"):                      ("api_key.creada",            CategoriaEvento.API_KEY),
    ("DELETE", "/api/v1/api-keys"):                      ("api_key.revocada",          CategoriaEvento.API_KEY),
    # Movilidad — Cuentas
    ("POST",   "/api/v1/movilidad/cuentas"):             ("movilidad.cuenta_creada",   CategoriaEvento.SISTEMA),
    ("GET",    "/api/v1/movilidad/cuentas"):             ("movilidad.cuentas_listadas",CategoriaEvento.DATOS),
    # Movilidad — Traslados
    ("POST",   "/api/v1/movilidad/traslados"):           ("movilidad.traslado_creado", CategoriaEvento.SISTEMA),
    ("PATCH",  "/api/v1/movilidad/traslados"):           ("movilidad.traslado_actualizado",CategoriaEvento.SISTEMA),
    # Movilidad — Radicaciones
    ("POST",   "/api/v1/movilidad/radicaciones"):        ("movilidad.radicacion_creada",CategoriaEvento.SISTEMA),
    ("PATCH",  "/api/v1/movilidad/radicaciones"):        ("movilidad.radicacion_actualizada",CategoriaEvento.SISTEMA),
    # Auditoría (lecturas sensibles)
    ("GET",    "/api/v1/auditoria"):                     ("auditoria.consultada",      CategoriaEvento.DATOS),
    ("GET",    "/api/v1/auditoria/estadisticas"):        ("auditoria.estadisticas",    CategoriaEvento.DATOS),
    ("GET",    "/api/v1/auditoria/exportar"):            ("auditoria.exportada",       CategoriaEvento.DATOS),
    ("GET",    "/api/v1/auditoria/verificar-integridad"):("auditoria.integridad_verificada", CategoriaEvento.DATOS),
}


def _determinar_accion_categoria(method: str, path: str) -> tuple[str, CategoriaEvento]:
    """Busca en el mapa. Si no encuentra, infiere desde los segmentos del path."""
    key = (method, path)
    if key in _ACCIONES:
        return _ACCIONES[key]

    # Buscar por path padre (rutas dinámicas como /api/v1/usuarios/{id})
    partes = path.rstrip("/").split("/")
    for depth in range(1, 4):
        parent = "/".join(partes[:-depth])
        if parent:
            found = _ACCIONES.get((method, parent))
            if found:
                return found

    # Fallback: derivar desde segmentos
    segs = [s for s in path.split("/") if s]
    recurso = segs[2] if len(segs) > 2 else "desconocido"
    return f"{method.lower()}.{recurso}", CategoriaEvento.SISTEMA


def _determinar_nivel(status: int, categoria: CategoriaEvento, accion: str) -> NivelEvento:
    if status == 403:
        return NivelEvento.SEGURIDAD
    if status == 401:
        return NivelEvento.ADVERTENCIA
    if status == 429:
        return NivelEvento.SEGURIDAD
    if status >= 500:
        return NivelEvento.CRITICO
    if "exportada" in accion:
        return NivelEvento.CRITICO
    if categoria == CategoriaEvento.SEGURIDAD:
        return NivelEvento.SEGURIDAD
    if status >= 400:
        return NivelEvento.ADVERTENCIA
    if categoria == CategoriaEvento.DATOS and status == 200:
        return NivelEvento.ADVERTENCIA
    return NivelEvento.INFO


def _sanitizar(obj: Any) -> Any:
    """Elimina valores sensibles de un dict recursivamente."""
    if not isinstance(obj, dict):
        return obj
    return {
        k: "***" if k.lower() in _CAMPOS_SENSIBLES else _sanitizar(v)
        for k, v in obj.items()
    }


async def _leer_body(request: Request, max_bytes: int = 8_192) -> dict[str, Any] | None:
    """Lee y sanitiza el body JSON. Devuelve None si es demasiado grande o no es JSON."""
    try:
        raw = await request.body()
        if not raw or len(raw) > max_bytes:
            return None
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return _sanitizar(parsed)
        return None
    except Exception:
        return None


def _query_params_sanitizados(request: Request) -> dict[str, str] | None:
    params = dict(request.query_params)
    if not params:
        return None
    return {k: "***" if k.lower() in _CAMPOS_SENSIBLES else v for k, v in params.items()}


class AuditoriaMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next) -> Response:
        if not config.AUDIT_ENABLED:
            return await call_next(request)

        path = request.url.path
        if path in _EXCLUIR_EXACTOS or path.startswith(_EXCLUIR_PREFIJOS):
            return await call_next(request)

        method = request.method
        es_mutacion = method in ("POST", "PATCH", "PUT", "DELETE")
        es_get_sensible = method == "GET" and any(
            path == p or path.startswith(p + "/") for p in _GET_AUDITADOS
        )

        if not es_mutacion and not es_get_sensible:
            return await call_next(request)

        # Leer body ANTES de call_next (Starlette lo cachea, no se pierde)
        body_sanitizado = await _leer_body(request) if es_mutacion else None
        inicio = time.perf_counter()

        response = await call_next(request)

        duracion_ms = int((time.perf_counter() - inicio) * 1000)
        asyncio.create_task(
            self._registrar_safe(request, response, body_sanitizado, duracion_ms)
        )
        return response

    async def _registrar_safe(
        self,
        request: Request,
        response: Response,
        body: dict | None,
        duracion_ms: int,
    ) -> None:
        try:
            await self._registrar(request, response, body, duracion_ms)
        except Exception:
            logger.error("AuditoriaMiddleware: error al registrar evento", exc_info=True)

    async def _registrar(
        self,
        request: Request,
        response: Response,
        body: dict | None,
        duracion_ms: int,
    ) -> None:
        from app.infrastructure.persistence.database import AsyncSessionFactory
        from app.infrastructure.persistence.repositorios.auth.auditoria_repo import AuditoriaRepositorioSQL
        from sqlalchemy import text as sa_text

        status = response.status_code
        path   = request.url.path

        # Actor
        actor_id    = getattr(request.state, "usuario_id",    None)
        actor_email = getattr(request.state, "usuario_email", None)
        actor_tipo  = TipoActor.USUARIO if actor_id else TipoActor.ANONIMO
        org_id      = getattr(request.state, "organization_id", None)
        sesion_id   = getattr(request.state, "sesion_id",     None)
        api_key_id  = getattr(request.state, "api_key_id",    None)

        # Resultado HTTP
        if status < 400:
            resultado = ResultadoAuditoria.EXITOSO
        elif status == 403:
            resultado = ResultadoAuditoria.DENEGADO
        else:
            resultado = ResultadoAuditoria.FALLIDO

        # Acción y categoría
        path_limpio = path.split("?")[0]
        accion, categoria = _determinar_accion_categoria(request.method, path_limpio)
        nivel = _determinar_nivel(status, categoria, accion)

        # Recurso
        segs         = [s for s in path_limpio.split("/") if s]
        recurso_tipo = segs[2] if len(segs) > 2 else ""
        recurso_id   = getattr(request.state, "audit_recurso_id",    None)
        val_anterior = getattr(request.state, "audit_valor_anterior", None)
        val_nuevo    = getattr(request.state, "audit_valor_nuevo",    None)
        razon        = getattr(request.state, "audit_razon",          None)
        res_detalle  = getattr(request.state, "audit_resultado_detalle", None)

        # Metadatos base
        metadatos: dict = {
            "fuente":      "middleware",
            "status_code": status,
            "path":        path_limpio,
        }
        if body:
            metadatos["body"] = body

        registro = RegistroAuditoria(
            correlation_id    = getattr(request.state, "correlation_id", ""),
            actor_id          = actor_id,
            actor_email       = actor_email,
            actor_ip          = request.client.host if request.client else "",
            actor_user_agent  = request.headers.get("User-Agent", ""),
            actor_tipo        = actor_tipo,
            sesion_id         = sesion_id,
            api_key_id        = api_key_id,
            accion            = accion,
            resultado         = resultado,
            resultado_detalle = res_detalle,
            categoria         = categoria,
            nivel             = nivel,
            metodo_http       = request.method,
            path              = path_limpio,
            query_params      = _query_params_sanitizados(request),
            codigo_respuesta  = status,
            duracion_ms       = duracion_ms,
            recurso_tipo      = recurso_tipo,
            recurso_id        = recurso_id,
            valor_anterior    = val_anterior,
            valor_nuevo       = val_nuevo,
            razon             = razon,
            metadatos         = metadatos,
            organization_id   = org_id,
        )

        async with AsyncSessionFactory() as session:
            tenant    = str(org_id) if (config.MULTITENANCY_ENABLED and org_id) else ""
            uid_str   = str(actor_id) if actor_id else ""
            await session.execute(
                sa_text(
                    "SELECT set_config('app.current_tenant',  :t,   true),"
                    "       set_config('app.current_user_id', :uid, true)"
                ),
                {"t": tenant, "uid": uid_str},
            )
            repo = AuditoriaRepositorioSQL(session)
            await repo.registrar(registro)
            await session.commit()
