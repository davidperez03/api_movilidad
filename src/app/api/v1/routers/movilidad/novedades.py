from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.repositorios.movilidad.novedad_repo import NovedadRepositorioSQL
from app.infrastructure.persistence.repositorios.movilidad.traslado_repo import TrasladoRepositorioSQL
from app.infrastructure.persistence.repositorios.movilidad.radicacion_repo import RadicacionRepositorioSQL
from app.application.use_cases.movilidad.crear_novedad import CrearNovedadUseCase, ComandoCrearNovedad
from app.application.use_cases.movilidad.resolver_novedad import ResolverNovedadUseCase, ComandoResolverNovedad
from app.domain.ports.outbound.movilidad.repositorio_novedad import FiltrosNovedad
from app.domain.entities.auth.usuario import Usuario
from app.domain.entities.movilidad.novedad import EstadoNovedad
from app.domain.exceptions import EntidadNoEncontrada
from app.api.v1.schemas.movilidad.novedad import (
    CrearNovedadRequest, ResolverNovedadRequest, NovedadResponse,
)
from app.api.v1.schemas.paginacion import PaginaResponse
from app.dependencies import requiere_permiso, get_organization_id

router = APIRouter()

_PERM_LEER    = "movilidad.novedades:leer"
_PERM_CREAR   = "movilidad.novedades:crear"
_PERM_RESOLVER = "movilidad.novedades:resolver"


def _map(n) -> NovedadResponse:
    return NovedadResponse(
        id=n.public_id,
        proceso_tipo=n.proceso_tipo,
        proceso_id=n.proceso_id,
        tipo_novedad=n.tipo_novedad,
        prioridad=n.prioridad,
        descripcion=n.descripcion,
        estado=n.estado,
        solucion=n.solucion,
        resuelto_por=n.resuelto_por,
        resuelto_en=n.resuelto_en,
        creado_en=n.creado_en,
    )


@router.post("", response_model=NovedadResponse, status_code=201)
async def crear_novedad(
    body: CrearNovedadRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    usuario: Usuario = Depends(requiere_permiso(_PERM_CREAR)),
    org_id: UUID | None = Depends(get_organization_id),
):
    novedad = await CrearNovedadUseCase(
        NovedadRepositorioSQL(session),
        TrasladoRepositorioSQL(session),
        RadicacionRepositorioSQL(session),
    ).ejecutar(ComandoCrearNovedad(
        proceso_tipo=body.proceso_tipo,
        proceso_public_id=body.proceso_public_id,
        tipo_novedad=body.tipo_novedad,
        descripcion=body.descripcion,
        prioridad=body.prioridad,
        creado_por=usuario.id,
        organization_id=org_id,
    ))
    request.state.audit_recurso_id = novedad.public_id
    return _map(novedad)


@router.get("", response_model=PaginaResponse[NovedadResponse])
async def listar_novedades(
    traslado_id: UUID | None = Query(None),
    radicacion_id: UUID | None = Query(None),
    estado: EstadoNovedad | None = Query(None),
    cursor: str | None = Query(None),
    tamanio: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso(_PERM_LEER)),
    org_id: UUID | None = Depends(get_organization_id),
):
    pagina = await NovedadRepositorioSQL(session).listar(
        FiltrosNovedad(
            traslado_id=traslado_id,
            radicacion_id=radicacion_id,
            estado=estado,
            tamanio=tamanio,
            cursor=cursor,
            organization_id=org_id,
        )
    )
    return PaginaResponse(
        items=[_map(n) for n in pagina.items],
        siguiente_cursor=pagina.siguiente_cursor,
        total=pagina.tamanio,
    )


@router.get("/{public_id}", response_model=NovedadResponse)
async def obtener_novedad(
    public_id: str,
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso(_PERM_LEER)),
):
    n = await NovedadRepositorioSQL(session).buscar_por_public_id(public_id)
    if not n:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Novedad no encontrada")
    return _map(n)


@router.patch("/{public_id}/resolver", response_model=NovedadResponse)
async def resolver_novedad(
    public_id: str,
    body: ResolverNovedadRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    usuario: Usuario = Depends(requiere_permiso(_PERM_RESOLVER)),
):
    novedad = await ResolverNovedadUseCase(
        NovedadRepositorioSQL(session),
        TrasladoRepositorioSQL(session),
        RadicacionRepositorioSQL(session),
    ).ejecutar(ComandoResolverNovedad(
        novedad_public_id=public_id,
        solucion=body.solucion,
        actor_id=usuario.id,
    ))
    request.state.audit_recurso_id = novedad.public_id
    request.state.audit_valor_nuevo = {"estado": novedad.estado.value}
    return _map(novedad)
