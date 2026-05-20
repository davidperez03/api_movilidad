from uuid import UUID
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.repositorios.auth.usuario_repo import UsuarioRepositorioSQL
from app.infrastructure.persistence.repositorios.auth.rol_repo import RolRepositorioSQL
from app.infrastructure.security.auth.hash_service import BcryptHashService
from app.application.use_cases.auth.usuarios.crear_usuario import CrearUsuarioUseCase, ComandoCrearUsuario
from app.application.use_cases.auth.usuarios.actualizar_usuario import ActualizarUsuarioUseCase, ComandoActualizarUsuario
from app.application.use_cases.auth.usuarios.cambiar_estado_usuario import CambiarEstadoUsuarioUseCase, ComandoCambiarEstado
from app.application.use_cases.auth.usuarios.listar_usuarios import ListarUsuariosUseCase
from app.domain.ports.outbound.auth.repositorio_usuario import FiltrosUsuario
from app.domain.entities.auth.usuario import Usuario, EstadoUsuario
from app.api.v1.schemas.auth.usuario import (
    CrearUsuarioRequest, ActualizarUsuarioRequest, CambiarEstadoRequest,
    UsuarioResponse, UsuarioDetalleResponse, UsuarioResumen,
    PaginaUsuariosResponse,
)
from app.dependencies import get_usuario_actual, requiere_permiso, get_organization_id
from app.api.v1.mappers.auth.usuario_mapper import map_usuario, map_usuario_detalle
from app.application.use_cases.auth.usuarios._tasks import enviar_verificacion_email_bg

router = APIRouter()


async def _resolver_usuario(public_id: str, session: AsyncSession) -> Usuario:
    repo = UsuarioRepositorioSQL(session)
    u = await repo.buscar_por_public_id(public_id)
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Usuario '{public_id}' no encontrado")
    return u


@router.post("", response_model=UsuarioResponse, status_code=201)
async def crear_usuario(
    body: CrearUsuarioRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso("usuarios:crear")),
    org_id: UUID | None = Depends(get_organization_id),
):
    repo = UsuarioRepositorioSQL(session)
    repo_rol = RolRepositorioSQL(session)
    usuario = await CrearUsuarioUseCase(repo, repo_rol, BcryptHashService()).ejecutar(
        ComandoCrearUsuario(
            email=body.email,
            nombre=body.nombre,
            apellido=body.apellido,
            password=body.password.get_secret_value(),
            organization_id=org_id,
        )
    )
    request.state.audit_recurso_id = usuario.public_id
    request.state.audit_valor_nuevo = {"email": usuario.email, "nombre": usuario.nombre_completo, "rol": "usuario"}
    background_tasks.add_task(enviar_verificacion_email_bg, usuario.id, usuario.email, usuario.nombre)
    return map_usuario(usuario)


@router.get("", response_model=PaginaUsuariosResponse)
async def listar_usuarios(
    estado: EstadoUsuario | None = Query(None),
    busqueda: str | None = Query(None, max_length=100),
    cursor: str | None = Query(None, description="Token de paginación (opaco, del campo siguiente_cursor)"),
    tamanio: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso("usuarios:leer")),
    org_id: UUID | None = Depends(get_organization_id),
):
    repo = UsuarioRepositorioSQL(session)
    pagina_result = await ListarUsuariosUseCase(repo).ejecutar(
        FiltrosUsuario(estado=estado, busqueda=busqueda, tamanio=tamanio, cursor=cursor),
        organization_id=org_id,
    )
    return PaginaUsuariosResponse(
        items=[
            UsuarioResumen(
                id=u.public_id,
                email=u.email,
                nombre_completo=u.nombre_completo,
                estado=u.estado,
            )
            for u in pagina_result.items
        ],
        siguiente_cursor=pagina_result.siguiente_cursor,
        tamanio=pagina_result.tamanio,
        tiene_siguiente=pagina_result.tiene_siguiente,
    )


@router.get("/me", response_model=UsuarioDetalleResponse)
async def mi_perfil(
    usuario_actual: Usuario = Depends(get_usuario_actual),
    session: AsyncSession = Depends(get_session),
):
    repo_rol = RolRepositorioSQL(session)
    roles = await repo_rol.obtener_roles_de_usuario(usuario_actual.id)
    return map_usuario_detalle(usuario_actual, roles)


@router.get("/{public_id}", response_model=UsuarioDetalleResponse)
async def obtener_usuario(
    public_id: str,
    session: AsyncSession = Depends(get_session),
    usuario_actual: Usuario = Depends(get_usuario_actual),
):
    puede_ver_cualquiera = usuario_actual.tiene_permiso("usuarios:leer")
    es_propio = usuario_actual.public_id == public_id

    if not puede_ver_cualquiera and not es_propio:
        # Devolver 404 en vez de 403 — evita revelar si el usuario existe (IDOR)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    u = await _resolver_usuario(public_id, session)
    repo_rol = RolRepositorioSQL(session)
    roles = await repo_rol.obtener_roles_de_usuario(u.id)

    # Ocultar roles si el solicitante no tiene permisos de administración
    roles_visibles = roles if puede_ver_cualquiera else []
    return map_usuario_detalle(u, roles_visibles)


@router.patch("/{public_id}", response_model=UsuarioResponse)
async def actualizar_usuario(
    public_id: str,
    body: ActualizarUsuarioRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    usuario_actual: Usuario = Depends(get_usuario_actual),
):
    u = await _resolver_usuario(public_id, session)
    repo = UsuarioRepositorioSQL(session)
    u = await ActualizarUsuarioUseCase(repo, BcryptHashService()).ejecutar(
        ComandoActualizarUsuario(
            usuario_id=u.id,
            solicitante_id=usuario_actual.id,
            puede_editar_cualquier_usuario=usuario_actual.tiene_permiso("usuarios:editar"),
            nombre=body.nombre,
            apellido=body.apellido,
            password_actual=body.password_actual.get_secret_value() if body.password_actual else None,
            nueva_password=body.nueva_password.get_secret_value() if body.nueva_password else None,
        )
    )
    cambios = {}
    if body.nombre:
        cambios["nombre"] = body.nombre
    if body.apellido:
        cambios["apellido"] = body.apellido
    if body.nueva_password:
        cambios["password"] = "modificado"
    request.state.audit_recurso_id = public_id
    request.state.audit_valor_nuevo = cambios
    return map_usuario(u)


@router.patch("/{public_id}/estado", response_model=UsuarioResponse)
async def cambiar_estado_usuario(
    public_id: str,
    body: CambiarEstadoRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    usuario_actual: Usuario = Depends(requiere_permiso("usuarios:suspender")),
):
    u = await _resolver_usuario(public_id, session)
    repo = UsuarioRepositorioSQL(session)
    u, estado_anterior = await CambiarEstadoUsuarioUseCase(repo).ejecutar(
        ComandoCambiarEstado(
            usuario_id=u.id,
            solicitante_id=usuario_actual.id,
            nuevo_estado=body.estado,
            puede_administrar_usuarios=True,
            razon=body.razon,
        )
    )
    request.state.audit_recurso_id = public_id
    request.state.audit_valor_anterior = {"estado": estado_anterior.value}
    request.state.audit_valor_nuevo = {"estado": body.estado.value}
    request.state.audit_razon = body.razon
    return map_usuario(u)
