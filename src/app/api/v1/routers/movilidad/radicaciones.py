from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.repositorios.movilidad.traslado_repo import TrasladoRepositorioSQL
from app.infrastructure.persistence.repositorios.movilidad.radicacion_repo import RadicacionRepositorioSQL
from app.infrastructure.services.movilidad.dias_habiles import DiasHabilesService
from app.application.use_cases.movilidad.crear_radicacion import CrearRadicacionUseCase, ComandoCrearRadicacion
from app.application.use_cases.movilidad.cambiar_estado_radicacion import (
    CambiarEstadoRadicacionUseCase, ComandoCambiarEstadoRadicacion,
)
from app.domain.ports.outbound.movilidad.repositorio_radicacion import FiltrosRadicacion
from app.domain.entities.auth.usuario import Usuario
from app.domain.entities.movilidad.radicacion import EstadoRadicacion
from app.domain.exceptions import ReglaDeNegocioViolada, EntidadNoEncontrada
from app.api.v1.schemas.movilidad.radicacion import (
    CrearRadicacionRequest, CambiarEstadoRadicacionRequest, RadicacionResponse,
)
from app.dependencies import requiere_permiso, get_organization_id

router = APIRouter()


def _map_radicacion(r) -> RadicacionResponse:
    return RadicacionResponse(
        id=r.public_id,
        cuenta_id=r.cuenta_id,
        traslado_id=r.traslado_id,
        organismo_id=r.organismo_id,
        estado=r.estado,
        numero_radicado=r.numero_radicado,
        observaciones=r.observaciones,
        vence_en=r.vence_en,
        completado_en=r.completado_en,
        creado_en=r.creado_en,
        transiciones_disponibles=r.transiciones_disponibles(),
    )


@router.post("", response_model=RadicacionResponse, status_code=201)
async def crear_radicacion(
    body: CrearRadicacionRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    usuario: Usuario = Depends(requiere_permiso("movilidad:crear_radicacion")),
    org_id: UUID | None = Depends(get_organization_id),
):
    try:
        radicacion = await CrearRadicacionUseCase(
            repo_traslado=TrasladoRepositorioSQL(session),
            repo_radicacion=RadicacionRepositorioSQL(session),
            svc_dias=DiasHabilesService(session),
        ).ejecutar(ComandoCrearRadicacion(
            traslado_public_id=body.traslado_public_id,
            organismo_id=body.organismo_id,
            creado_por=usuario.id,
            organization_id=org_id,
        ))
        request.state.audit_recurso_id = radicacion.public_id
        return _map_radicacion(radicacion)
    except EntidadNoEncontrada as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ReglaDeNegocioViolada as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("", response_model=list[RadicacionResponse])
async def listar_radicaciones(
    cuenta_id: UUID | None = Query(None),
    traslado_id: UUID | None = Query(None),
    estado: EstadoRadicacion | None = Query(None),
    vencidos: bool | None = Query(None),
    cursor: str | None = Query(None),
    tamanio: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso("movilidad:ver_vehiculos")),
    org_id: UUID | None = Depends(get_organization_id),
):
    repo = RadicacionRepositorioSQL(session)
    pagina = await repo.listar(FiltrosRadicacion(
        cuenta_id=cuenta_id, traslado_id=traslado_id, estado=estado, vencidos=vencidos,
        tamanio=tamanio, cursor=cursor, organization_id=org_id,
    ))
    return [_map_radicacion(r) for r in pagina.items]


@router.get("/{public_id}", response_model=RadicacionResponse)
async def obtener_radicacion(
    public_id: str,
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso("movilidad:ver_vehiculos")),
):
    repo = RadicacionRepositorioSQL(session)
    r = await repo.buscar_por_public_id(public_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Radicación no encontrada")
    return _map_radicacion(r)


@router.patch("/{public_id}/estado", response_model=RadicacionResponse)
async def cambiar_estado_radicacion(
    public_id: str,
    body: CambiarEstadoRadicacionRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    usuario: Usuario = Depends(requiere_permiso("movilidad:revisar_radicacion")),
):
    try:
        radicacion = await CambiarEstadoRadicacionUseCase(RadicacionRepositorioSQL(session)).ejecutar(
            ComandoCambiarEstadoRadicacion(
                radicacion_public_id=public_id,
                nuevo_estado=body.nuevo_estado,
                motivo=body.motivo,
                numero_radicado=body.numero_radicado,
                actor_id=usuario.id,
            )
        )
        request.state.audit_recurso_id = radicacion.public_id
        request.state.audit_valor_nuevo = {"estado": radicacion.estado.value}
        return _map_radicacion(radicacion)
    except EntidadNoEncontrada as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ReglaDeNegocioViolada as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
