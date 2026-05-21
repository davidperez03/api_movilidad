from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.repositorios.movilidad.cuenta_repo import CuentaRepositorioSQL
from app.application.use_cases.movilidad.crear_cuenta import CrearCuentaUseCase, ComandoCrearCuenta
from app.domain.ports.outbound.movilidad.repositorio_cuenta import FiltrosCuenta
from app.domain.entities.auth.usuario import Usuario
from app.domain.exceptions import ReglaDeNegocioViolada
from app.api.v1.schemas.movilidad.cuenta import (
    CrearCuentaRequest, CuentaResponse, ConsultaPublicaCuentaResponse,
)
from app.dependencies import requiere_permiso, get_organization_id

router = APIRouter()


def _map(c) -> CuentaResponse:
    return CuentaResponse(
        id=c.public_id,
        numero_cuenta=c.numero_cuenta,
        placa=c.placa,
        tipo_servicio=c.tipo_servicio,
        creado_en=c.creado_en,
    )


@router.post("", response_model=CuentaResponse, status_code=201)
async def crear_cuenta(
    body: CrearCuentaRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    usuario: Usuario = Depends(requiere_permiso("movilidad.cuentas:crear")),
    org_id: UUID | None = Depends(get_organization_id),
):
    try:
        cuenta = await CrearCuentaUseCase(CuentaRepositorioSQL(session)).ejecutar(
            ComandoCrearCuenta(
                placa=body.placa,
                tipo_servicio=body.tipo_servicio,
                creado_por=usuario.id,
                organization_id=org_id,
            )
        )
        request.state.audit_recurso_id = cuenta.public_id
        return _map(cuenta)
    except ReglaDeNegocioViolada as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("", response_model=list[CuentaResponse])
async def listar_cuentas(
    placa: str | None = Query(None),
    cursor: str | None = Query(None),
    tamanio: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso("movilidad.cuentas:leer")),
    org_id: UUID | None = Depends(get_organization_id),
):
    repo = CuentaRepositorioSQL(session)
    pagina = await repo.listar(FiltrosCuenta(placa=placa, tamanio=tamanio, cursor=cursor, organization_id=org_id))
    return [_map(c) for c in pagina.items]


@router.get("/consulta", response_model=ConsultaPublicaCuentaResponse)
async def consulta_publica(
    placa: str = Query(..., min_length=5, max_length=10),
    session: AsyncSession = Depends(get_session),
):
    """Sin autenticación — consulta de placa pública."""
    repo = CuentaRepositorioSQL(session)
    cuenta = await repo.buscar_por_placa(placa.upper())
    if not cuenta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Placa no encontrada")
    return ConsultaPublicaCuentaResponse(
        numero_cuenta=cuenta.numero_cuenta,
        placa=cuenta.placa,
        tipo_servicio=cuenta.tipo_servicio,
    )


@router.get("/{public_id}", response_model=CuentaResponse)
async def obtener_cuenta(
    public_id: str,
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso("movilidad.cuentas:leer")),
):
    repo = CuentaRepositorioSQL(session)
    cuenta = await repo.buscar_por_public_id(public_id)
    if not cuenta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cuenta no encontrada")
    return _map(cuenta)
