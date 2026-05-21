from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.repositorios.parqueadero.vehiculo_repo import VehiculoRepositorioSQL
from app.infrastructure.persistence.repositorios.parqueadero.inspeccion_repo import InspeccionRepositorioSQL
from app.application.use_cases.parqueadero.crear_inspeccion import CrearInspeccionUseCase, ComandoCrearInspeccion
from app.domain.ports.outbound.parqueadero.repositorio_inspeccion import FiltrosInspeccion
from app.domain.entities.auth.usuario import Usuario
from app.domain.exceptions import ReglaDeNegocioViolada, EntidadNoEncontrada
from app.api.v1.schemas.parqueadero.inspeccion import (
    CrearInspeccionRequest, AprobarInspeccionRequest, InspeccionResponse,
)
from app.dependencies import requiere_permiso, get_organization_id

router = APIRouter()


def _map(ins) -> InspeccionResponse:
    return InspeccionResponse(
        id=ins.public_id,
        codigo=ins.codigo,
        vehiculo_id=ins.vehiculo_id,
        operador_id=ins.operador_id,
        inspector_id=ins.inspector_id,
        auxiliar_id=ins.auxiliar_id,
        fecha=ins.fecha,
        hora=ins.hora,
        turno=ins.turno,
        es_apto=ins.es_apto,
        observaciones=ins.observaciones,
        firma_operador=ins.firma_operador,
        firma_inspector=ins.firma_inspector,
        fotos=ins.fotos,
        soat_vencimiento_snap=ins.soat_vencimiento_snap,
        tecnomecanica_vencimiento_snap=ins.tecnomecanica_vencimiento_snap,
        licencia_vencimiento_snap=ins.licencia_vencimiento_snap,
        creado_en=ins.creado_en,
    )


@router.post("", response_model=InspeccionResponse, status_code=201)
async def crear_inspeccion(
    body: CrearInspeccionRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    usuario: Usuario = Depends(requiere_permiso("parqueadero.inspecciones:crear")),
    org_id: UUID | None = Depends(get_organization_id),
):
    try:
        ins = await CrearInspeccionUseCase(
            VehiculoRepositorioSQL(session), InspeccionRepositorioSQL(session),
        ).ejecutar(ComandoCrearInspeccion(
            vehiculo_public_id=body.vehiculo_public_id,
            operador_id=body.operador_id,
            inspector_id=body.inspector_id,
            auxiliar_id=body.auxiliar_id,
            fecha=body.fecha,
            hora=body.hora,
            turno=body.turno,
            observaciones=body.observaciones,
            fotos=body.fotos,
            soat_vencimiento_snap=body.soat_vencimiento_snap,
            tecnomecanica_vencimiento_snap=body.tecnomecanica_vencimiento_snap,
            licencia_vencimiento_snap=body.licencia_vencimiento_snap,
            creado_por=usuario.id,
            organization_id=org_id,
        ))
        request.state.audit_recurso_id = ins.public_id
        return _map(ins)
    except EntidadNoEncontrada as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ReglaDeNegocioViolada as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("", response_model=list[InspeccionResponse])
async def listar_inspecciones(
    vehiculo_id: UUID | None = Query(None),
    es_apto: bool | None = Query(None),
    cursor: str | None = Query(None),
    tamanio: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso("parqueadero.inspecciones:crear")),
    org_id: UUID | None = Depends(get_organization_id),
):
    pagina = await InspeccionRepositorioSQL(session).listar(
        FiltrosInspeccion(vehiculo_id=vehiculo_id, es_apto=es_apto,
                          tamanio=tamanio, cursor=cursor, organization_id=org_id)
    )
    return [_map(ins) for ins in pagina.items]


@router.get("/{public_id}", response_model=InspeccionResponse)
async def obtener_inspeccion(
    public_id: str,
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso("parqueadero.inspecciones:crear")),
):
    ins = await InspeccionRepositorioSQL(session).buscar_por_public_id(public_id)
    if not ins:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspección no encontrada")
    return _map(ins)


@router.patch("/{public_id}/aprobar", response_model=InspeccionResponse)
async def aprobar_inspeccion(
    public_id: str,
    body: AprobarInspeccionRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    usuario: Usuario = Depends(requiere_permiso("parqueadero.inspecciones:aprobar")),
):
    from datetime import datetime, timezone
    repo = InspeccionRepositorioSQL(session)
    ins = await repo.buscar_por_public_id(public_id)
    if not ins:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspección no encontrada")

    ins.es_apto = body.es_apto
    ins.firma_operador = body.firma_operador
    ins.firma_inspector = body.firma_inspector
    if body.observaciones:
        ins.observaciones = body.observaciones
    ins.actualizado_por = usuario.id
    ins.actualizado_en = datetime.now(timezone.utc)

    ins = await repo.actualizar(ins)
    request.state.audit_recurso_id = ins.public_id
    request.state.audit_valor_nuevo = {"es_apto": ins.es_apto}
    return _map(ins)
