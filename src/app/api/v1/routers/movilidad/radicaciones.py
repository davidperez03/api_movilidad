from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.repositorios.movilidad.cuenta_repo import CuentaRepositorioSQL
from app.infrastructure.persistence.repositorios.movilidad.traslado_repo import TrasladoRepositorioSQL
from app.infrastructure.persistence.repositorios.movilidad.radicacion_repo import RadicacionRepositorioSQL
from app.infrastructure.persistence.repositorios.movilidad.notificacion_repo import NotificacionRadicacionRepositorioSQL
from app.application.use_cases.movilidad.crear_radicacion import CrearRadicacionUseCase, ComandoCrearRadicacion
from app.application.use_cases.movilidad.cambiar_estado_radicacion import (
    CambiarEstadoRadicacionUseCase, ComandoCambiarEstadoRadicacion,
)
from app.domain.ports.outbound.movilidad.repositorio_radicacion import FiltrosRadicacion
from app.domain.entities.auth.usuario import Usuario
from app.domain.entities.movilidad.radicacion import EstadoRadicacion
from app.domain.exceptions import EntidadNoEncontrada
from app.api.v1.schemas.movilidad.radicacion import (
    CrearRadicacionRequest, CambiarEstadoRadicacionRequest, RadicacionResponse,
)
from app.api.v1.schemas.paginacion import PaginaResponse
from app.api.v1.routers.movilidad._shared import dias_restantes as _dias_restantes
from app.dependencies import requiere_permiso, get_organization_id

router = APIRouter()


def _map(r) -> RadicacionResponse:
    return RadicacionResponse(
        id=r.public_id,
        cuenta_id=r.cuenta_id,
        organismo_origen_id=r.organismo_origen_id,
        empresa_transportadora_id=r.empresa_transportadora_id,
        estado=r.estado,
        numero_guia=r.numero_guia,
        numero_guia_devolucion=r.numero_guia_devolucion,
        observaciones=r.observaciones,
        radicado_en=r.radicado_en,
        vencimiento=r.vencimiento,
        completado_en=r.completado_en,
        creado_en=r.creado_en,
        transiciones_disponibles=r.transiciones_disponibles(),
        dias_restantes=_dias_restantes(r.vencimiento, r.esta_activo),
    )


@router.post("", response_model=RadicacionResponse, status_code=201)
async def crear_radicacion(
    body: CrearRadicacionRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    usuario: Usuario = Depends(requiere_permiso("movilidad.radicaciones:crear")),
    org_id: UUID | None = Depends(get_organization_id),
):
    radicacion = await CrearRadicacionUseCase(
        CuentaRepositorioSQL(session),
        TrasladoRepositorioSQL(session),
        RadicacionRepositorioSQL(session),
    ).ejecutar(ComandoCrearRadicacion(
        cuenta_public_id=body.cuenta_public_id,
        organismo_origen_id=body.organismo_origen_id,
        empresa_transportadora_id=body.empresa_transportadora_id,
        creado_por=usuario.id,
        organization_id=org_id,
    ))
    request.state.audit_recurso_id = radicacion.public_id
    return _map(radicacion)


@router.get("", response_model=PaginaResponse[RadicacionResponse])
async def listar_radicaciones(
    cuenta_id: UUID | None = Query(None),
    estado: EstadoRadicacion | None = Query(None),
    vencidos: bool | None = Query(None),
    cursor: str | None = Query(None),
    tamanio: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso("movilidad.radicaciones:leer")),
    org_id: UUID | None = Depends(get_organization_id),
):
    pagina = await RadicacionRepositorioSQL(session).listar(
        FiltrosRadicacion(cuenta_id=cuenta_id, estado=estado, vencidos=vencidos,
                          tamanio=tamanio, cursor=cursor, organization_id=org_id)
    )
    return PaginaResponse(
        items=[_map(r) for r in pagina.items],
        siguiente_cursor=pagina.siguiente_cursor,
        total=pagina.tamanio,
    )


@router.get("/{public_id}", response_model=RadicacionResponse)
async def obtener_radicacion(
    public_id: str,
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso("movilidad.radicaciones:leer")),
):
    r = await RadicacionRepositorioSQL(session).buscar_por_public_id(public_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Radicación no encontrada")
    return _map(r)


@router.patch("/{public_id}/estado", response_model=RadicacionResponse)
async def cambiar_estado_radicacion(
    public_id: str,
    body: CambiarEstadoRadicacionRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    usuario: Usuario = Depends(requiere_permiso("movilidad.radicaciones:revisar")),
):
    radicacion = await CambiarEstadoRadicacionUseCase(RadicacionRepositorioSQL(session)).ejecutar(
        ComandoCambiarEstadoRadicacion(
            radicacion_public_id=public_id,
            nuevo_estado=body.nuevo_estado,
            motivo=body.motivo,
            numero_guia=body.numero_guia,
            numero_guia_devolucion=body.numero_guia_devolucion,
            organismo_origen_id=body.organismo_origen_id,
            empresa_transportadora_id=body.empresa_transportadora_id,
            actor_id=usuario.id,
        )
    )
    request.state.audit_recurso_id = radicacion.public_id
    request.state.audit_valor_nuevo = {"estado": radicacion.estado.value}
    return _map(radicacion)


from pydantic import BaseModel


class MarcarNotificadoRequest(BaseModel):
    observaciones: str = ""


@router.patch("/{public_id}/notificacion", status_code=200)
async def marcar_solicitante_notificado(
    public_id: str,
    body: MarcarNotificadoRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    usuario: Usuario = Depends(requiere_permiso("movilidad.radicaciones:revisar")),
):
    """Registra que el solicitante fue notificado sobre el estado de su radicación."""
    repo_rad = RadicacionRepositorioSQL(session)
    radicacion = await repo_rad.buscar_por_public_id(public_id)
    if not radicacion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Radicación no encontrada")

    notif = await NotificacionRadicacionRepositorioSQL(session).marcar_notificado(
        radicacion_id=radicacion.id,
        observaciones=body.observaciones or None,
        actor_id=usuario.id,
    )
    request.state.audit_recurso_id = public_id
    request.state.audit_valor_nuevo = {"solicitante_notificado": True}
    return {
        "radicacion_id": public_id,
        "solicitante_notificado": notif.solicitante_notificado,
        "notificado_en": notif.notificado_en,
        "observaciones": notif.observaciones,
    }
