from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import requiere_permiso
from app.domain.entities.auth.auditoria import CategoriaEvento, NivelEvento, ResultadoAuditoria
from app.domain.entities.auth.usuario import Usuario
from app.domain.ports.outbound.auth.repositorio_auditoria import FiltrosAuditoria
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.repositorios.auth.auditoria_repo import AuditoriaRepositorioSQL
from app.infrastructure.persistence.repositorios.auth.usuario_repo import UsuarioRepositorioSQL
from app.api.v1.schemas.auth.auditoria import (
    EstadisticasAuditoriaResponse,
    PaginaAuditoriaResponse,
    RegistroAuditoriaResponse,
    ResultadoVerificacionResponse,
)

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _a_response(r) -> RegistroAuditoriaResponse:
    return RegistroAuditoriaResponse(
        id                = r.id,
        numero_secuencia  = r.numero_secuencia,
        timestamp         = r.timestamp,
        timestamp_unix_ms = r.timestamp_unix_ms,
        correlation_id    = r.correlation_id,
        actor_id          = r.actor_id,
        actor_email       = r.actor_email,
        actor_ip          = r.actor_ip,
        actor_user_agent  = r.actor_user_agent,
        actor_tipo        = r.actor_tipo,
        sesion_id         = r.sesion_id,
        api_key_id        = r.api_key_id,
        categoria         = r.categoria,
        nivel             = r.nivel,
        accion            = r.accion,
        resultado         = r.resultado,
        resultado_detalle = r.resultado_detalle,
        metodo_http       = r.metodo_http,
        path              = r.path,
        query_params      = r.query_params,
        codigo_respuesta  = r.codigo_respuesta,
        duracion_ms       = r.duracion_ms,
        recurso_tipo      = r.recurso_tipo,
        recurso_id        = r.recurso_id,
        valor_anterior    = r.valor_anterior,
        valor_nuevo       = r.valor_nuevo,
        diferencia        = r.diferencia,
        metadatos         = r.metadatos,
        razon             = r.razon,
        error_mensaje     = r.error_mensaje,
        hash_registro     = r.hash_registro,
        firma_hmac        = r.firma_hmac,
    )


# ── GET /auditoria — listado con filtros ──────────────────────────────────────

@router.get("", response_model=PaginaAuditoriaResponse)
async def listar_auditoria(
    # Filtros por actor
    actor_public_id: str | None = Query(None, description="public_id del actor (usr_xxx)"),
    actor_ip:        str | None = Query(None, max_length=45),
    sesion_id:       str | None = Query(None, max_length=100),
    # Filtros por recurso
    recurso_tipo: str | None = Query(None, max_length=100),
    recurso_id:   str | None = Query(None, max_length=100),
    # Filtros por evento
    accion:      str | None             = Query(None, max_length=200),
    categoria:   CategoriaEvento | None = Query(None),
    nivel:       NivelEvento | None     = Query(None),
    resultado:   ResultadoAuditoria | None = Query(None),
    metodo_http: str | None             = Query(None, max_length=10),
    codigo_respuesta: int | None        = Query(None, ge=100, le=599),
    # Rango temporal
    desde: datetime | None = Query(None),
    hasta: datetime | None = Query(None),
    # Paginación
    cursor:  str | None = Query(None, description="Token opaco del campo siguiente_cursor"),
    tamanio: int        = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
    usuario: Usuario      = Depends(requiere_permiso("auditoria:leer")),
):
    if desde and hasta and desde > hasta:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="'desde' no puede ser mayor que 'hasta'",
        )

    actor_id = None
    if actor_public_id:
        repo_usr = UsuarioRepositorioSQL(session)
        actor    = await repo_usr.buscar_por_public_id(actor_public_id)
        if not actor:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Actor '{actor_public_id}' no encontrado")
        actor_id = actor.id

    org_id = usuario.organization_id if hasattr(usuario, "organization_id") else None

    repo     = AuditoriaRepositorioSQL(session)
    filtros  = FiltrosAuditoria(
        actor_id         = actor_id,
        actor_ip         = actor_ip,
        sesion_id        = sesion_id,
        recurso_tipo     = recurso_tipo,
        recurso_id       = recurso_id,
        accion           = accion,
        categoria        = categoria,
        nivel            = nivel,
        resultado        = resultado,
        metodo_http      = metodo_http,
        codigo_respuesta = codigo_respuesta,
        desde            = desde,
        hasta            = hasta,
        tamanio          = tamanio,
        cursor           = cursor,
    )
    registros, total, siguiente_cursor = await repo.listar(filtros, organization_id=org_id)

    return PaginaAuditoriaResponse(
        items           = [_a_response(r) for r in registros],
        total           = total,
        tamanio         = tamanio,
        siguiente_cursor = siguiente_cursor,
        tiene_siguiente  = siguiente_cursor is not None,
    )


# ── GET /auditoria/{id} — detalle de un registro ──────────────────────────────

@router.get("/{registro_id}", response_model=RegistroAuditoriaResponse)
async def obtener_registro(
    registro_id: UUID,
    session: AsyncSession = Depends(get_session),
    _: Usuario            = Depends(requiere_permiso("auditoria:leer")),
):
    repo     = AuditoriaRepositorioSQL(session)
    registro = await repo.obtener_por_id(registro_id)
    if not registro:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Registro de auditoría no encontrado")
    return _a_response(registro)


# ── GET /auditoria/estadisticas — resumen para dashboard ─────────────────────

@router.get("/estadisticas/resumen", response_model=EstadisticasAuditoriaResponse)
async def estadisticas(
    desde: datetime | None = Query(None, description="Inicio del período (default: últimos 30 días)"),
    hasta: datetime | None = Query(None, description="Fin del período (default: ahora)"),
    session: AsyncSession = Depends(get_session),
    usuario: Usuario      = Depends(requiere_permiso("auditoria:leer")),
):
    org_id = usuario.organization_id if hasattr(usuario, "organization_id") else None
    repo   = AuditoriaRepositorioSQL(session)
    stats  = await repo.estadisticas(organization_id=org_id, desde=desde, hasta=hasta)

    return EstadisticasAuditoriaResponse(
        total_eventos               = stats.total_eventos,
        por_categoria               = stats.por_categoria,
        por_nivel                   = stats.por_nivel,
        por_resultado               = stats.por_resultado,
        eventos_seguridad_24h       = stats.eventos_seguridad_24h,
        eventos_criticos_24h        = stats.eventos_criticos_24h,
        intentos_fallidos_login_24h = stats.intentos_fallidos_login_24h,
        periodo_desde               = stats.periodo_desde,
        periodo_hasta               = stats.periodo_hasta,
    )


# ── GET /auditoria/verificar-integridad — cadena de custodia HMAC ─────────────

@router.get("/integridad/verificar")
async def verificar_integridad(
    desde:  datetime | None = Query(None),
    hasta:  datetime | None = Query(None),
    limite: int             = Query(5000, ge=100, le=20_000, description="Máx registros a verificar"),
    session: AsyncSession = Depends(get_session),
    usuario: Usuario      = Depends(requiere_permiso("auditoria:leer")),
):
    """
    Verifica la firma HMAC de cada registro firmado en el rango dado.
    - HTTP 200: todos los registros firmados son íntegros.
    - HTTP 409: al menos un registro fue alterado — incluye los IDs corruptos.
    - Los registros de trigger BD (firma vacía) se cuentan en total_sin_firma pero no fallan.
    """
    org_id  = usuario.organization_id if hasattr(usuario, "organization_id") else None
    repo    = AuditoriaRepositorioSQL(session)
    result  = await repo.verificar_integridad(
        organization_id=org_id, desde=desde, hasta=hasta, limite=limite
    )

    response_body = ResultadoVerificacionResponse(
        total_verificados = result.total_verificados,
        total_ok          = result.total_ok,
        total_fallidos    = result.total_fallidos,
        total_sin_firma   = result.total_sin_firma,
        integro           = result.integro,
        ids_fallidos      = result.ids_fallidos,
        verificado_en     = result.verificado_en,
    )

    if not result.integro:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=response_body.model_dump(mode="json"),
        )
    return response_body


# ── GET /auditoria/exportar — descarga completa para auditorías externas ──────

@router.get("/exportar/json", response_model=list[RegistroAuditoriaResponse])
async def exportar(
    desde:  datetime | None = Query(None),
    hasta:  datetime | None = Query(None),
    limite: int             = Query(10_000, ge=1, le=10_000),
    session: AsyncSession = Depends(get_session),
    usuario: Usuario      = Depends(requiere_permiso("auditoria:exportar")),
):
    """
    Exporta registros de auditoría en JSON para empresas auditoras externas.
    Requiere permiso 'auditoria:exportar' (más restrictivo que 'auditoria:leer').
    Máximo 10 000 registros por solicitud — paginar con filtros de fecha si se necesita más.
    """
    org_id    = usuario.organization_id if hasattr(usuario, "organization_id") else None
    repo      = AuditoriaRepositorioSQL(session)
    registros = await repo.exportar(
        organization_id=org_id, desde=desde, hasta=hasta, limite=limite
    )
    return [_a_response(r) for r in registros]
