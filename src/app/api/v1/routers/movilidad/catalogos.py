from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.repositorios.movilidad.organismo_repo import OrganismoRepositorioSQL
from app.infrastructure.persistence.repositorios.movilidad.empresa_repo import EmpresaRepositorioSQL
from app.domain.entities.auth.usuario import Usuario
from app.domain.entities.movilidad.organismo import OrganismoTransito
from app.domain.entities.movilidad.empresa import EmpresaTransporte
from app.api.v1.schemas.movilidad.reporte import OrganismoResponse, EmpresaResponse
from app.dependencies import requiere_permiso

_PERM_LEER     = "movilidad.cuentas:leer"
_PERM_GESTIONAR = "movilidad.cuentas:editar"


class CrearOrganismoRequest(BaseModel):
    nombre: str = Field(..., min_length=3, max_length=300)
    municipio: str = Field(..., min_length=2, max_length=200)
    departamento: str = Field(..., min_length=2, max_length=200)
    tipo: str = Field("", max_length=100)
    telefono: Optional[str] = Field(None, max_length=50)
    direccion: Optional[str] = Field(None, max_length=500)


class CrearEmpresaRequest(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=300)

router = APIRouter()

_PERM_LEER = "movilidad.cuentas:leer"


def _map_org(o: OrganismoTransito) -> OrganismoResponse:
    return OrganismoResponse(
        id=o.public_id,
        nombre=o.nombre,
        tipo=getattr(o, "tipo", ""),
        municipio=o.municipio,
        departamento=o.departamento,
        telefono=getattr(o, "telefono", None),
        direccion=getattr(o, "direccion", None),
        activo=o.activo,
    )


def _map_emp(e: EmpresaTransporte) -> EmpresaResponse:
    return EmpresaResponse(id=e.public_id, nombre=e.nombre, activo=e.activo)


# ── Organismos de tránsito ────────────────────────────────────────────────────

@router.get("/organismos", response_model=list[OrganismoResponse])
async def listar_organismos(
    q: str | None = Query(None, description="Búsqueda por nombre, municipio o departamento"),
    departamento: str | None = Query(None),
    solo_activos: bool = Query(True),
    tamanio: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso(_PERM_LEER)),
):
    items = await OrganismoRepositorioSQL(session).listar(
        q=q, departamento=departamento, solo_activos=solo_activos,
        tamanio=tamanio, offset=offset,
    )
    return [_map_org(o) for o in items]


@router.get("/organismos/{public_id}", response_model=OrganismoResponse)
async def obtener_organismo(
    public_id: str,
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso(_PERM_LEER)),
):
    org = await OrganismoRepositorioSQL(session).buscar_por_public_id(public_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organismo no encontrado")
    return _map_org(org)


@router.post("/organismos", response_model=OrganismoResponse, status_code=201)
async def crear_organismo(
    body: CrearOrganismoRequest,
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso(_PERM_GESTIONAR)),
):
    org = OrganismoTransito(nombre=body.nombre, codigo="", municipio=body.municipio, departamento=body.departamento)
    org.tipo = body.tipo
    org.telefono = body.telefono
    org.direccion = body.direccion
    org = await OrganismoRepositorioSQL(session).guardar(org)
    return _map_org(org)


# ── Empresas transportadoras ──────────────────────────────────────────────────

@router.get("/empresas", response_model=list[EmpresaResponse])
async def listar_empresas(
    q: str | None = Query(None, description="Búsqueda por nombre"),
    solo_activos: bool = Query(True),
    tamanio: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso(_PERM_LEER)),
):
    items = await EmpresaRepositorioSQL(session).listar(
        q=q, solo_activos=solo_activos, tamanio=tamanio, offset=offset,
    )
    return [_map_emp(e) for e in items]


@router.get("/empresas/{public_id}", response_model=EmpresaResponse)
async def obtener_empresa(
    public_id: str,
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso(_PERM_LEER)),
):
    emp = await EmpresaRepositorioSQL(session).buscar_por_public_id(public_id)
    if not emp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa no encontrada")
    return _map_emp(emp)


@router.post("/empresas", response_model=EmpresaResponse, status_code=201)
async def crear_empresa(
    body: CrearEmpresaRequest,
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso(_PERM_GESTIONAR)),
):
    emp = EmpresaTransporte(nombre=body.nombre, nit="")
    emp = await EmpresaRepositorioSQL(session).guardar(emp)
    return _map_emp(emp)
