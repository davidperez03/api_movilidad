from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.repositorios.parqueadero.vehiculo_repo import VehiculoRepositorioSQL
from app.application.use_cases.parqueadero.crear_vehiculo import CrearVehiculoUseCase, ComandoCrearVehiculo
from app.domain.ports.outbound.parqueadero.repositorio_vehiculo import FiltrosVehiculo
from app.domain.entities.auth.usuario import Usuario
from app.domain.exceptions import EntidadNoEncontrada
from app.api.v1.schemas.parqueadero.vehiculo import (
    CrearVehiculoRequest, ActualizarVehiculoRequest, VehiculoResponse,
)
from app.api.v1.schemas.paginacion import PaginaResponse
from app.dependencies import requiere_permiso, get_organization_id

router = APIRouter()


def _map(v) -> VehiculoResponse:
    return VehiculoResponse(
        id=v.public_id,
        placa=v.placa,
        tipo_vehiculo=v.tipo_vehiculo,
        marca=v.marca,
        modelo=v.modelo,
        soat_aseguradora=v.soat_aseguradora,
        soat_vencimiento=v.soat_vencimiento,
        tecnomecanica_vencimiento=v.tecnomecanica_vencimiento,
        activo=v.activo,
        creado_en=v.creado_en,
    )


@router.post("", response_model=VehiculoResponse, status_code=201)
async def crear_vehiculo(
    body: CrearVehiculoRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    usuario: Usuario = Depends(requiere_permiso("parqueadero.vehiculos:gestionar")),
    org_id: UUID | None = Depends(get_organization_id),
):
    v = await CrearVehiculoUseCase(VehiculoRepositorioSQL(session)).ejecutar(
        ComandoCrearVehiculo(
            placa=body.placa,
            tipo_vehiculo=body.tipo_vehiculo,
            marca=body.marca,
            modelo=body.modelo,
            soat_aseguradora=body.soat_aseguradora,
            soat_vencimiento=body.soat_vencimiento,
            tecnomecanica_vencimiento=body.tecnomecanica_vencimiento,
            creado_por=usuario.id,
            organization_id=org_id,
        )
    )
    request.state.audit_recurso_id = v.public_id
    return _map(v)


@router.get("", response_model=PaginaResponse[VehiculoResponse])
async def listar_vehiculos(
    placa: str | None = Query(None),
    activo: bool | None = Query(None),
    cursor: str | None = Query(None),
    tamanio: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso("parqueadero.vehiculos:gestionar")),
    org_id: UUID | None = Depends(get_organization_id),
):
    pagina = await VehiculoRepositorioSQL(session).listar(
        FiltrosVehiculo(placa=placa, activo=activo, tamanio=tamanio, cursor=cursor, organization_id=org_id)
    )
    return PaginaResponse(items=[_map(v) for v in pagina.items], siguiente_cursor=pagina.siguiente_cursor, total=pagina.tamanio)


@router.get("/{public_id}", response_model=VehiculoResponse)
async def obtener_vehiculo(
    public_id: str,
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso("parqueadero.vehiculos:gestionar")),
):
    v = await VehiculoRepositorioSQL(session).buscar_por_public_id(public_id)
    if not v:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehículo no encontrado")
    return _map(v)


@router.patch("/{public_id}", response_model=VehiculoResponse)
async def actualizar_vehiculo(
    public_id: str,
    body: ActualizarVehiculoRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    usuario: Usuario = Depends(requiere_permiso("parqueadero.vehiculos:gestionar")),
):
    from datetime import datetime, timezone
    repo = VehiculoRepositorioSQL(session)
    v = await repo.buscar_por_public_id(public_id)
    if not v:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehículo no encontrado")
    if body.marca is not None:
        v.marca = body.marca
    if body.modelo is not None:
        v.modelo = body.modelo
    if body.tipo_vehiculo is not None:
        v.tipo_vehiculo = body.tipo_vehiculo
    if body.soat_aseguradora is not None:
        v.soat_aseguradora = body.soat_aseguradora
    if body.soat_vencimiento is not None:
        v.soat_vencimiento = body.soat_vencimiento
    if body.tecnomecanica_vencimiento is not None:
        v.tecnomecanica_vencimiento = body.tecnomecanica_vencimiento
    v.actualizado_en = datetime.now(timezone.utc)
    v = await repo.actualizar(v)
    request.state.audit_recurso_id = v.public_id
    return _map(v)
