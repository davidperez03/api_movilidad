from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.repositorios.nunc.sesion_repo import SesionNuncRepositorioSQL
from app.application.use_cases.nunc.crear_sesion import CrearSesionNuncUseCase, ComandoCrearSesionNunc
from app.application.use_cases.nunc.crear_registro import CrearRegistroNuncUseCase, ComandoCrearRegistroNunc
from app.domain.ports.outbound.nunc.repositorio_sesion import FiltrosRegistroNunc
from app.domain.entities.auth.usuario import Usuario
from app.domain.exceptions import EntidadNoEncontrada, ReglaDeNegocioViolada
from app.api.v1.schemas.nunc.sesion import (
    CrearSesionNuncRequest, SesionNuncResponse,
    ValidarSesionRequest, ValidarSesionResponse,
    CrearRegistroRequest, RegistroNuncResponse,
)
from app.dependencies import requiere_permiso, get_organization_id

router = APIRouter()


def _map_sesion(s) -> SesionNuncResponse:
    return SesionNuncResponse(
        id=s.public_id,
        codigo_sesion=s.codigo_sesion,
        nombre_entidad=s.nombre_entidad,
        nombre_perito=s.nombre_perito,
        estado=s.estado,
        expiracion=s.expiracion,
        creado_en=s.creado_en,
    )


def _map_registro(r) -> RegistroNuncResponse:
    return RegistroNuncResponse(
        id=r.public_id,
        sesion_id=r.sesion_id,
        placa=r.placa,
        departamento=r.departamento,
        municipio=r.municipio,
        entidad=r.entidad,
        unidad=r.unidad,
        ano=r.ano,
        numero_secuencial=r.numero_secuencial,
        creado_en=r.creado_en,
    )


@router.post("/sesiones", response_model=SesionNuncResponse, status_code=201)
async def crear_sesion(
    body: CrearSesionNuncRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    usuario: Usuario = Depends(requiere_permiso("nunc.sesiones:crear")),
    org_id: UUID | None = Depends(get_organization_id),
):
    sesion = await CrearSesionNuncUseCase(SesionNuncRepositorioSQL(session)).ejecutar(
        ComandoCrearSesionNunc(
            nombre_entidad=body.nombre_entidad,
            nombre_perito=body.nombre_perito,
            departamento=body.departamento,
            municipio=body.municipio,
            entidad=body.entidad,
            unidad=body.unidad,
            ano=body.ano,
            creado_por=usuario.id,
            organization_id=org_id,
        )
    )
    request.state.audit_recurso_id = sesion.public_id
    return _map_sesion(sesion)


@router.post("/validar", response_model=ValidarSesionResponse)
async def validar_sesion(
    body: ValidarSesionRequest,
    session: AsyncSession = Depends(get_session),
):
    """Sin autenticación — valida código NUNC."""
    repo = SesionNuncRepositorioSQL(session)
    sesion = await repo.buscar_sesion_por_codigo(body.codigo)
    if not sesion or not sesion.esta_activa:
        return ValidarSesionResponse(valida=False, codigo=body.codigo, mensaje="Código inválido o sesión expirada")
    return ValidarSesionResponse(valida=True, codigo=sesion.codigo_sesion, expiracion=sesion.expiracion, mensaje="Sesión activa")


@router.post("/registros", response_model=RegistroNuncResponse, status_code=201)
async def crear_registro(
    body: CrearRegistroRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    usuario: Usuario = Depends(requiere_permiso("nunc.registros:crear")),
    org_id: UUID | None = Depends(get_organization_id),
):
    try:
        registro = await CrearRegistroNuncUseCase(SesionNuncRepositorioSQL(session)).ejecutar(
            ComandoCrearRegistroNunc(
                sesion_codigo=body.sesion_codigo,
                placa=body.placa,
                departamento=body.departamento,
                municipio=body.municipio,
                entidad=body.entidad,
                unidad=body.unidad,
                ano=body.ano,
                organization_id=org_id,
            )
        )
        request.state.audit_recurso_id = registro.public_id
        return _map_registro(registro)
    except EntidadNoEncontrada as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ReglaDeNegocioViolada as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("/registros", response_model=list[RegistroNuncResponse])
async def listar_registros(
    sesion_id: UUID | None = Query(None),
    placa: str | None = Query(None),
    cursor: str | None = Query(None),
    tamanio: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso("nunc.reportes:leer")),
    org_id: UUID | None = Depends(get_organization_id),
):
    repo = SesionNuncRepositorioSQL(session)
    pagina = await repo.listar_registros(
        FiltrosRegistroNunc(sesion_id=sesion_id, placa=placa, tamanio=tamanio, cursor=cursor, organization_id=org_id)
    )
    return [_map_registro(r) for r in pagina.items]
