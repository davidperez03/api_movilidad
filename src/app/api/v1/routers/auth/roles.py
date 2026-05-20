from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.repositorios.auth.rol_repo import RolRepositorioSQL
from app.infrastructure.persistence.repositorios.auth.usuario_repo import UsuarioRepositorioSQL
from app.infrastructure.cache.redis_service import RedisService
from app.application.use_cases.auth.roles.crear_rol import CrearRolUseCase, ComandoCrearRol
from app.application.use_cases.auth.roles.asignar_permiso_a_rol import AsignarPermisoARolUseCase, ComandoAsignarPermiso
from app.application.use_cases.auth.roles.asignar_rol_a_usuario import AsignarRolAUsuarioUseCase, ComandoAsignarRolAUsuario
from app.application.use_cases.auth.roles.revocar_rol_de_usuario import RevocarRolDeUsuarioUseCase, ComandoRevocarRol
from app.api.v1.schemas.auth.rol import (
    CrearRolRequest, RolResponse, PermisoResponse, AsignarPermisoRequest, AsignarRolRequest,
)
from uuid import UUID
from app.domain.entities.auth.usuario import Usuario
from app.dependencies import requiere_permiso, get_organization_id
from app.api.v1.mappers.auth.rol_mapper import map_rol, map_permiso
from app.config import config as _cfg

router = APIRouter()


async def _resolver_rol(public_id: str, session: AsyncSession):
    repo = RolRepositorioSQL(session)
    r = await repo.buscar_rol_por_public_id(public_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rol '{public_id}' no encontrado")
    return r


@router.get("", response_model=list[RolResponse])
async def listar_roles(
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso("roles:leer")),
    org_id: UUID | None = Depends(get_organization_id),
):
    repo = RolRepositorioSQL(session)
    return [map_rol(r) for r in await repo.listar_roles(organization_id=org_id)]


@router.post("", response_model=RolResponse, status_code=201)
async def crear_rol(
    body: CrearRolRequest,
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso("roles:crear")),
):
    repo = RolRepositorioSQL(session)
    rol = await CrearRolUseCase(repo).ejecutar(ComandoCrearRol(nombre=body.nombre, descripcion=body.descripcion))
    return map_rol(rol)


@router.get("/permisos", response_model=list[PermisoResponse])
async def listar_permisos(
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso("roles:leer")),
):
    repo = RolRepositorioSQL(session)
    return [map_permiso(p) for p in await repo.listar_permisos()]


@router.post("/{rol_public_id}/permisos", response_model=RolResponse)
async def asignar_permiso(
    rol_public_id: str,
    body: AsignarPermisoRequest,
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso("roles:editar")),
):
    rol = await _resolver_rol(rol_public_id, session)
    repo = RolRepositorioSQL(session)
    permisos = await repo.listar_permisos()
    permiso = next((p for p in permisos if p.clave == body.permiso_clave), None)
    if not permiso:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Permiso '{body.permiso_clave}' no encontrado")
    rol = await AsignarPermisoARolUseCase(repo).ejecutar(
        ComandoAsignarPermiso(rol_id=rol.id, permiso_id=permiso.id)
    )
    return map_rol(rol)


@router.post("/asignar", status_code=201)
async def asignar_rol_a_usuario(
    body: AsignarRolRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    actor: Usuario = Depends(requiere_permiso("usuarios:asignar_rol")),
    org_id: UUID | None = Depends(get_organization_id),
):
    repo = RolRepositorioSQL(session)
    repo_usuario = UsuarioRepositorioSQL(session)
    cache = RedisService()

    usuario = await repo_usuario.buscar_por_public_id(body.usuario_public_id)
    if not usuario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Usuario '{body.usuario_public_id}' no encontrado")

    # Validar boundary de tenant: el usuario objetivo debe pertenecer al mismo tenant
    if _cfg.MULTITENANCY_ENABLED and org_id and usuario.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puedes asignar roles a usuarios de otro tenant")

    rol = await repo.buscar_rol_por_public_id(body.rol_public_id)
    if not rol:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rol '{body.rol_public_id}' no encontrado")

    await AsignarRolAUsuarioUseCase(repo, repo_usuario, cache).ejecutar(
        ComandoAsignarRolAUsuario(
            usuario_id=usuario.id,
            rol_id=rol.id,
            asignado_por_id=actor.id,
            vigente_hasta=body.vigente_hasta,
        )
    )

    # Invalidar cache de permisos inmediatamente tras cambio de rol
    await cache.delete(f"permisos_usuario:{usuario.id}")
    await cache.delete(f"usuario_perfil:{usuario.id}")

    request.state.audit_recurso_id = body.usuario_public_id
    request.state.audit_valor_nuevo = {"rol": body.rol_public_id}
    return {"mensaje": "Rol asignado correctamente"}


@router.delete("/revocar/{usuario_public_id}/{rol_public_id}", status_code=204)
async def revocar_rol(
    usuario_public_id: str,
    rol_public_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso("usuarios:asignar_rol")),
):
    repo = RolRepositorioSQL(session)
    repo_usuario = UsuarioRepositorioSQL(session)
    cache = RedisService()

    usuario = await repo_usuario.buscar_por_public_id(usuario_public_id)
    if not usuario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Usuario '{usuario_public_id}' no encontrado")

    rol = await repo.buscar_rol_por_public_id(rol_public_id)
    if not rol:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rol '{rol_public_id}' no encontrado")

    await RevocarRolDeUsuarioUseCase(repo, cache).ejecutar(
        ComandoRevocarRol(usuario_id=usuario.id, rol_id=rol.id)
    )

    # Invalidar cache de permisos inmediatamente tras revocación
    await cache.delete(f"permisos_usuario:{usuario.id}")
    await cache.delete(f"usuario_perfil:{usuario.id}")

    request.state.audit_recurso_id = usuario_public_id
    request.state.audit_valor_anterior = {"rol": rol_public_id}
