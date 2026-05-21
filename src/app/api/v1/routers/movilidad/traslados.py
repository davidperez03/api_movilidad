from datetime import date
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.repositorios.movilidad.cuenta_repo import CuentaRepositorioSQL
from app.infrastructure.persistence.repositorios.movilidad.traslado_repo import TrasladoRepositorioSQL
from app.infrastructure.persistence.repositorios.movilidad.radicacion_repo import RadicacionRepositorioSQL
from app.application.use_cases.movilidad.crear_traslado import CrearTrasladoUseCase, ComandoCrearTraslado
from app.application.use_cases.movilidad.cambiar_estado_traslado import (
    CambiarEstadoTrasladoUseCase, ComandoCambiarEstadoTraslado,
)
from app.domain.ports.outbound.movilidad.repositorio_traslado import FiltrosTraslado
from app.domain.entities.auth.usuario import Usuario
from app.domain.entities.movilidad.traslado import EstadoTraslado
from app.domain.exceptions import EntidadNoEncontrada
from app.api.v1.schemas.movilidad.traslado import (
    CrearTrasladoRequest, CambiarEstadoTrasladoRequest, TrasladoResponse,
)
import asyncio
from app.api.v1.schemas.paginacion import PaginaResponse
from app.api.v1.routers.movilidad._shared import dias_restantes as _dias_restantes
from app.dependencies import requiere_permiso, get_organization_id
from app.infrastructure.persistence.repositorios.movilidad.organismo_repo import OrganismoRepositorioSQL
from app.infrastructure.persistence.repositorios.movilidad.empresa_repo import EmpresaRepositorioSQL
from app.infrastructure.services.movilidad.pdf_service import generar_pdf_remision
from fastapi.responses import Response

router = APIRouter()


def _map(t) -> TrasladoResponse:
    return TrasladoResponse(
        id=t.public_id,
        cuenta_id=t.cuenta_id,
        organismo_destino_id=t.organismo_destino_id,
        empresa_transportadora_id=t.empresa_transportadora_id,
        estado=t.estado,
        numero_guia=t.numero_guia,
        observaciones=t.observaciones,
        aprobado_en=t.aprobado_en,
        vencimiento=t.vencimiento,
        completado_en=t.completado_en,
        creado_en=t.creado_en,
        transiciones_disponibles=t.transiciones_disponibles(),
        dias_restantes=_dias_restantes(t.vencimiento, t.esta_activo),
    )


@router.post("", response_model=TrasladoResponse, status_code=201)
async def crear_traslado(
    body: CrearTrasladoRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    usuario: Usuario = Depends(requiere_permiso("movilidad.traslados:crear")),
    org_id: UUID | None = Depends(get_organization_id),
):
    traslado = await CrearTrasladoUseCase(
        CuentaRepositorioSQL(session), TrasladoRepositorioSQL(session), RadicacionRepositorioSQL(session),
    ).ejecutar(ComandoCrearTraslado(
        cuenta_public_id=body.cuenta_public_id,
        organismo_destino_id=body.organismo_destino_id,
        empresa_transportadora_id=body.empresa_transportadora_id,
        creado_por=usuario.id,
        organization_id=org_id,
    ))
    request.state.audit_recurso_id = traslado.public_id
    return _map(traslado)


@router.get("", response_model=PaginaResponse[TrasladoResponse])
async def listar_traslados(
    cuenta_id: UUID | None = Query(None),
    estado: EstadoTraslado | None = Query(None),
    vencidos: bool | None = Query(None),
    cursor: str | None = Query(None),
    tamanio: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso("movilidad.traslados:leer")),
    org_id: UUID | None = Depends(get_organization_id),
):
    pagina = await TrasladoRepositorioSQL(session).listar(
        FiltrosTraslado(cuenta_id=cuenta_id, estado=estado, vencidos=vencidos,
                        tamanio=tamanio, cursor=cursor, organization_id=org_id)
    )
    return PaginaResponse(
        items=[_map(t) for t in pagina.items],
        siguiente_cursor=pagina.siguiente_cursor,
        total=pagina.tamanio,
    )


@router.get("/{public_id}", response_model=TrasladoResponse)
async def obtener_traslado(
    public_id: str,
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso("movilidad.traslados:leer")),
):
    t = await TrasladoRepositorioSQL(session).buscar_por_public_id(public_id)
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Traslado no encontrado")
    return _map(t)


@router.get("/{public_id}/remision.pdf", response_class=Response)
async def descargar_remision_pdf(
    public_id: str,
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso("movilidad.traslados:leer")),
):
    """Genera y descarga el documento de remisión del traslado en PDF."""
    repo_tra = TrasladoRepositorioSQL(session)
    repo_cue = CuentaRepositorioSQL(session)

    traslado = await repo_tra.buscar_por_public_id(public_id)
    if not traslado:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Traslado no encontrado")

    cuenta = await repo_cue.buscar_por_id(traslado.cuenta_id)

    async def _nombre_organismo() -> str | None:
        if not traslado.organismo_destino_id:
            return None
        org = await OrganismoRepositorioSQL(session).buscar_por_id(traslado.organismo_destino_id)
        return org.nombre if org else None

    async def _nombre_empresa() -> str | None:
        if not traslado.empresa_transportadora_id:
            return None
        emp = await EmpresaRepositorioSQL(session).buscar_por_id(traslado.empresa_transportadora_id)
        return emp.nombre if emp else None

    organismo_nombre, empresa_nombre = await asyncio.gather(_nombre_organismo(), _nombre_empresa())

    loop = asyncio.get_running_loop()
    pdf_bytes = await loop.run_in_executor(
        None,
        lambda: generar_pdf_remision(traslado, cuenta, organismo_nombre, empresa_nombre),
    )

    filename = f"remision-{public_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.patch("/{public_id}/estado", response_model=TrasladoResponse)
async def cambiar_estado_traslado(
    public_id: str,
    body: CambiarEstadoTrasladoRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    usuario: Usuario = Depends(requiere_permiso("movilidad.traslados:aprobar")),
):
    traslado = await CambiarEstadoTrasladoUseCase(TrasladoRepositorioSQL(session)).ejecutar(
        ComandoCambiarEstadoTraslado(
            traslado_public_id=public_id,
            nuevo_estado=body.nuevo_estado,
            motivo=body.motivo,
            numero_guia=body.numero_guia,
            organismo_destino_id=body.organismo_destino_id,
            empresa_transportadora_id=body.empresa_transportadora_id,
            actor_id=usuario.id,
        )
    )
    request.state.audit_recurso_id = traslado.public_id
    request.state.audit_valor_nuevo = {"estado": traslado.estado.value}
    return _map(traslado)
