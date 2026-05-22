import asyncio
from datetime import date
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.repositorios.movilidad.cuenta_repo import CuentaRepositorioSQL
from app.infrastructure.persistence.repositorios.movilidad.traslado_repo import TrasladoRepositorioSQL
from app.infrastructure.persistence.repositorios.movilidad.radicacion_repo import RadicacionRepositorioSQL
from app.application.use_cases.movilidad.crear_cuenta import CrearCuentaUseCase, ComandoCrearCuenta
from app.domain.ports.outbound.movilidad.repositorio_cuenta import FiltrosCuenta
from app.domain.ports.outbound.movilidad.repositorio_traslado import FiltrosTraslado
from app.domain.ports.outbound.movilidad.repositorio_radicacion import FiltrosRadicacion
from app.domain.entities.auth.usuario import Usuario
from app.api.v1.schemas.movilidad.cuenta import (
    CrearCuentaRequest, CuentaResponse, ConsultaPublicaCuentaResponse,
)
from app.api.v1.schemas.paginacion import PaginaResponse
from app.dependencies import requiere_permiso, get_organization_id
from app.infrastructure.services.movilidad.dias_habiles import DiasHabilesService

router = APIRouter()


def _map(c) -> CuentaResponse:
    return CuentaResponse(
        id=c.public_id,
        numero_cuenta=c.numero_cuenta,
        placa=c.placa,
        tipo_servicio=c.tipo_servicio,
        creado_en=c.creado_en,
    )


@router.post("", response_model=CuentaResponse, status_code=201,
             summary="Crear cuenta de movilidad")
async def crear_cuenta(
    body: CrearCuentaRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    usuario: Usuario = Depends(requiere_permiso("movilidad.cuentas:crear")),
    org_id: UUID | None = Depends(get_organization_id),
):
    """Registra una nueva cuenta asociada a una placa vehicular. La placa debe ser única."""
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


@router.get("", response_model=PaginaResponse[CuentaResponse],
            summary="Listar cuentas")
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
    return PaginaResponse(items=[_map(c) for c in pagina.items], siguiente_cursor=pagina.siguiente_cursor, total=pagina.tamanio)


@router.get("/consulta", response_model=ConsultaPublicaCuentaResponse)
async def consulta_publica(
    placa: str = Query(..., min_length=5, max_length=10),
    session: AsyncSession = Depends(get_session),
):
    """Sin autenticación — consulta de placa pública con estado del último proceso."""
    repo = CuentaRepositorioSQL(session)
    cuenta = await repo.buscar_por_placa(placa.upper())
    if not cuenta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Placa no encontrada")

    # Obtener el último proceso (traslado o radicación) por fecha de creación
    repo_tra = TrasladoRepositorioSQL(session)
    repo_rad = RadicacionRepositorioSQL(session)
    dias_svc = DiasHabilesService(session)

    pagina_tra, pagina_rad = await asyncio.gather(
        repo_tra.listar(FiltrosTraslado(cuenta_id=cuenta.id, tamanio=1)),
        repo_rad.listar(FiltrosRadicacion(cuenta_id=cuenta.id, tamanio=1)),
    )

    ultimo_traslado = pagina_tra.items[0] if pagina_tra.items else None
    ultima_rad = pagina_rad.items[0] if pagina_rad.items else None

    proceso_tipo = None
    proceso_estado = None
    fecha_vencimiento = None
    dias_restantes = None
    observaciones = None
    numero_guia = None
    organismo_id = None

    if ultimo_traslado and ultima_rad:
        usar_traslado = ultimo_traslado.creado_en >= ultima_rad.creado_en
    elif ultimo_traslado:
        usar_traslado = True
    elif ultima_rad:
        usar_traslado = False
    else:
        usar_traslado = None

    if usar_traslado is True:
        proceso_tipo = "traslado"
        proceso_estado = ultimo_traslado.estado.value
        fecha_vencimiento = ultimo_traslado.vencimiento
        organismo_id = ultimo_traslado.organismo_destino_id
        observaciones = ultimo_traslado.observaciones or None
        numero_guia = ultimo_traslado.numero_guia or None
        if fecha_vencimiento and ultimo_traslado.esta_activo:
            dias_restantes = await dias_svc.contar_dias_habiles(date.today(), fecha_vencimiento)
    elif usar_traslado is False:
        proceso_tipo = "radicacion"
        proceso_estado = ultima_rad.estado.value
        fecha_vencimiento = ultima_rad.vencimiento
        organismo_id = ultima_rad.organismo_origen_id
        observaciones = ultima_rad.observaciones or None
        numero_guia = ultima_rad.numero_guia or None
        if fecha_vencimiento and ultima_rad.esta_activo:
            dias_restantes = await dias_svc.contar_dias_habiles(date.today(), fecha_vencimiento)

    # Resolver nombre de organismo si existe
    ciudad = None
    if organismo_id:
        from sqlalchemy import text as sa_text
        result = await session.execute(
            sa_text("SELECT nombre FROM mov_organismos_transito WHERE id = :id"),
            {"id": organismo_id},
        )
        row = result.fetchone()
        if row:
            ciudad = row[0]

    return ConsultaPublicaCuentaResponse(
        numero_cuenta=cuenta.numero_cuenta,
        placa=cuenta.placa,
        tipo_servicio=cuenta.tipo_servicio,
        proceso_tipo=proceso_tipo,
        proceso_estado=proceso_estado,
        fecha_vencimiento=fecha_vencimiento,
        dias_restantes=dias_restantes,
        ciudad=ciudad,
        observaciones=observaciones,
        numero_guia=numero_guia,
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
