import pytest
from unittest.mock import AsyncMock
from uuid6 import uuid7
from app.application.use_cases.auth.roles.crear_rol import CrearRolUseCase, ComandoCrearRol
from app.application.use_cases.auth.roles.asignar_rol_a_usuario import AsignarRolAUsuarioUseCase, ComandoAsignarRolAUsuario
from app.application.use_cases.auth.roles.asignar_permiso_a_rol import AsignarPermisoARolUseCase, ComandoAsignarPermiso
from app.domain.entities.auth.rol import Rol, Permiso, AsignacionRol
from app.domain.exceptions import RolNoEncontrado, PermisoNoEncontrado, EntidadNoEncontrada


def _rol(nombre="editor"):
    return Rol(id=uuid7(), nombre=nombre, descripcion="desc")


def _permiso():
    return Permiso(id=uuid7(), recurso="roles", accion="leer", descripcion="")


@pytest.mark.asyncio
async def test_crear_rol_exitoso(mock_repo_rol):
    rol_nuevo = _rol()
    mock_repo_rol.guardar_rol = AsyncMock(return_value=rol_nuevo)

    resultado = await CrearRolUseCase(mock_repo_rol).ejecutar(
        ComandoCrearRol(nombre="editor", descripcion="desc")
    )

    assert resultado.nombre == "editor"
    mock_repo_rol.guardar_rol.assert_called_once()


@pytest.mark.asyncio
async def test_asignar_rol_a_usuario_exitoso(mock_repo_rol, mock_repo_usuario, mock_cache):
    rol = _rol()
    mock_repo_rol.buscar_rol_por_id = AsyncMock(return_value=rol)
    mock_repo_usuario.buscar_por_id = AsyncMock(return_value=None)
    mock_repo_rol.asignar_rol_a_usuario = AsyncMock(return_value=AsignacionRol(
        usuario_id=uuid7(), rol_id=rol.id
    ))

    usuario_id = uuid7()
    mock_repo_usuario.buscar_por_id = AsyncMock(return_value=None)

    from app.domain.entities.auth.usuario import Usuario, EstadoUsuario
    u = Usuario(id=usuario_id, email="x@x.com", nombre="X", apellido="Y", estado=EstadoUsuario.ACTIVO)
    mock_repo_usuario.buscar_por_id = AsyncMock(return_value=u)

    await AsignarRolAUsuarioUseCase(mock_repo_rol, mock_repo_usuario, mock_cache).ejecutar(
        ComandoAsignarRolAUsuario(usuario_id=usuario_id, rol_id=rol.id, asignado_por_id=uuid7())
    )

    mock_repo_rol.asignar_rol_a_usuario.assert_called_once()
    mock_cache.delete.assert_called_once()


@pytest.mark.asyncio
async def test_asignar_rol_rol_inexistente(mock_repo_rol, mock_repo_usuario, mock_cache):
    mock_repo_rol.buscar_rol_por_id = AsyncMock(return_value=None)

    with pytest.raises(RolNoEncontrado):
        await AsignarRolAUsuarioUseCase(mock_repo_rol, mock_repo_usuario, mock_cache).ejecutar(
            ComandoAsignarRolAUsuario(usuario_id=uuid7(), rol_id=uuid7(), asignado_por_id=uuid7())
        )


@pytest.mark.asyncio
async def test_asignar_permiso_a_rol_exitoso(mock_repo_rol):
    rol = _rol()
    permiso = _permiso()
    rol_actualizado = _rol()
    rol_actualizado.permisos = [permiso]

    mock_repo_rol.buscar_rol_por_id = AsyncMock(return_value=rol)
    mock_repo_rol.listar_permisos = AsyncMock(return_value=[permiso])
    mock_repo_rol.actualizar_rol = AsyncMock(return_value=rol_actualizado)

    resultado = await AsignarPermisoARolUseCase(mock_repo_rol).ejecutar(
        ComandoAsignarPermiso(rol_id=rol.id, permiso_id=permiso.id)
    )

    assert len(resultado.permisos) == 1
    assert resultado.permisos[0].clave == "roles:leer"


@pytest.mark.asyncio
async def test_asignar_permiso_rol_inexistente(mock_repo_rol):
    mock_repo_rol.buscar_rol_por_id = AsyncMock(return_value=None)

    with pytest.raises(RolNoEncontrado):
        await AsignarPermisoARolUseCase(mock_repo_rol).ejecutar(
            ComandoAsignarPermiso(rol_id=uuid7(), permiso_id=uuid7())
        )
