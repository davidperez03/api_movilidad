from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.repositorios.movilidad.cuenta_repo import CuentaRepositorioSQL
from app.infrastructure.persistence.repositorios.movilidad.traslado_repo import TrasladoRepositorioSQL
from app.infrastructure.services.movilidad.dias_habiles import DiasHabilesService
from app.application.use_cases.movilidad.crear_traslado import CrearTrasladoUseCase, ComandoCrearTraslado
from app.application.use_cases.movilidad.cambiar_estado_traslado import (
    CambiarEstadoTrasladoUseCase, ComandoCambiarEstadoTraslado,
)
from app.domain.ports.outbound.movilidad.repositorio_traslado import FiltrosTraslado
from app.domain.entities.auth.usuario import Usuario
from app.domain.entities.movilidad.traslado import EstadoTraslado
from app.domain.exceptions import ReglaDeNegocioViolada, EntidadNoEncontrada
from app.api.v1.schemas.movilidad.traslado import (
    CrearTrasladoRequest, CambiarEstadoTrasladoRequest, TrasladoResponse,
)
from app.dependencies import get_usuario_actual, requiere_permiso, get_organization_id

router = APIRouter()


def _map_traslado(t) -> TrasladoResponse:
    return TrasladoResponse(
        id=t.public_id,
        cuenta_id=t.cuenta_id,
        organismo_destino_id=t.organismo_destino_id,
        estado=t.estado,
        observaciones=t.observaciones,
        vence_en=t.vence_en,
        completado_en=t.completado_en,
        creado_en=t.creado_en,
        transiciones_disponibles=t.transiciones_disponibles(),
    )


@router.post("", response_model=TrasladoResponse, status_code=201)
async def crear_traslado(
    body: CrearTrasladoRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    usuario: Usuario = Depends(requiere_permiso("movilidad:crear_traslado")),
    org_id: UUID | None = Depends(get_organization_id),
):
    try:
        traslado = await CrearTrasladoUseCase(
            repo_cuenta=CuentaRepositorioSQL(session),
            repo_traslado=TrasladoRepositorioSQL(session),
            svc_dias=DiasHabilesService(session),
        ).ejecutar(ComandoCrearTraslado(
            cuenta_public_id=body.cuenta_public_id,
            organismo_destino_id=body.organismo_destino_id,
            creado_por=usuario.id,
            organization_id=org_id,
        ))
        request.state.audit_recurso_id = traslado.public_id
        return _map_traslado(traslado)
    except EntidadNoEncontrada as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ReglaDeNegocioViolada as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("", response_model=list[TrasladoResponse])
async def listar_traslados(
    cuenta_id: UUID | None = Query(None),
    estado: EstadoTraslado | None = Query(None),
    vencidos: bool | None = Query(None),
    cursor: str | None = Query(None),
    tamanio: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso("movilidad:ver_vehiculos")),
    org_id: UUID | None = Depends(get_organization_id),
):
    repo = TrasladoRepositorioSQL(session)
    pagina = await repo.listar(FiltrosTraslado(
        cuenta_id=cuenta_id, estado=estado, vencidos=vencidos,
        tamanio=tamanio, cursor=cursor, organization_id=org_id,
    ))
    return [_map_traslado(t) for t in pagina.items]


@router.get("/{public_id}", response_model=TrasladoResponse)
async def obtener_traslado(
    public_id: str,
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso("movilidad:ver_vehiculos")),
):
    repo = TrasladoRepositorioSQL(session)
    traslado = await repo.buscar_por_public_id(public_id)
    if not traslado:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Traslado no encontrado")
    return _map_traslado(traslado)


@router.patch("/{public_id}/estado", response_model=TrasladoResponse)
async def cambiar_estado_traslado(
    public_id: str,
    body: CambiarEstadoTrasladoRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    usuario: Usuario = Depends(requiere_permiso("movilidad:aprobar_traslado")),
):
    try:
        traslado = await CambiarEstadoTrasladoUseCase(TrasladoRepositorioSQL(session)).ejecutar(
            ComandoCambiarEstadoTraslado(
                traslado_public_id=public_id,
                nuevo_estado=body.nuevo_estado,
                motivo=body.motivo,
                actor_id=usuario.id,
            )
        )
        request.state.audit_recurso_id = traslado.public_id
        request.state.audit_valor_nuevo = {"estado": traslado.estado.value}
        return _map_traslado(traslado)
    except EntidadNoEncontrada as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ReglaDeNegocioViolada as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
