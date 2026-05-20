import pytest
from unittest.mock import AsyncMock
from uuid6 import uuid7
from app.application.use_cases.auth.usuarios.crear_usuario import CrearUsuarioUseCase, ComandoCrearUsuario
from app.domain.entities.auth.usuario import Usuario, EstadoUsuario
from app.domain.entities.auth.rol import Rol, AsignacionRol
from app.domain.exceptions import EmailYaRegistrado, RolNoEncontrado


def _rol_usuario():
    return Rol(id=uuid7(), nombre="usuario", descripcion="Rol base")


@pytest.mark.asyncio
async def test_crear_usuario_exitoso(mock_repo_usuario, mock_repo_rol, mock_hash):
    usuario_nuevo = Usuario(id=uuid7(), email="nuevo@ejemplo.com", nombre="Ana", apellido="García")
    mock_repo_usuario.guardar = AsyncMock(return_value=usuario_nuevo)
    mock_repo_rol.buscar_rol_por_nombre = AsyncMock(return_value=_rol_usuario())
    mock_repo_rol.asignar_rol_a_usuario = AsyncMock(return_value=AsignacionRol(
        usuario_id=usuario_nuevo.id, rol_id=uuid7()
    ))

    use_case = CrearUsuarioUseCase(mock_repo_usuario, mock_repo_rol, mock_hash)
    resultado = await use_case.ejecutar(
        ComandoCrearUsuario(email="nuevo@ejemplo.com", nombre="Ana", apellido="García", password="Segura1")
    )

    assert resultado.email == "nuevo@ejemplo.com"
    mock_repo_usuario.guardar.assert_called_once()
    mock_hash.hashear.assert_called_once_with("Segura1")


@pytest.mark.asyncio
async def test_crear_usuario_email_duplicado(mock_repo_usuario, mock_repo_rol, mock_hash):
    mock_repo_usuario.existe_email = AsyncMock(return_value=True)

    use_case = CrearUsuarioUseCase(mock_repo_usuario, mock_repo_rol, mock_hash)
    with pytest.raises(EmailYaRegistrado):
        await use_case.ejecutar(
            ComandoCrearUsuario(email="dup@ejemplo.com", nombre="X", apellido="Y", password="Segura1")
        )

    mock_repo_usuario.guardar.assert_not_called()


@pytest.mark.asyncio
async def test_crear_usuario_rol_inexistente(mock_repo_usuario, mock_repo_rol, mock_hash):
    mock_repo_rol.buscar_rol_por_nombre = AsyncMock(return_value=None)

    use_case = CrearUsuarioUseCase(mock_repo_usuario, mock_repo_rol, mock_hash)
    with pytest.raises(RolNoEncontrado):
        await use_case.ejecutar(
            ComandoCrearUsuario(email="x@ejemplo.com", nombre="X", apellido="Y", password="Segura1")
        )


@pytest.mark.asyncio
async def test_crear_usuario_normaliza_email(mock_repo_usuario, mock_repo_rol, mock_hash):
    mock_repo_rol.buscar_rol_por_nombre = AsyncMock(return_value=_rol_usuario())
    capturado = {}

    async def guardar_capturando(usuario, hash_pw):
        capturado["usuario"] = usuario
        capturado["hash"] = hash_pw
        return usuario

    mock_repo_usuario.guardar = guardar_capturando
    mock_repo_rol.asignar_rol_a_usuario = AsyncMock(return_value=None)

    use_case = CrearUsuarioUseCase(mock_repo_usuario, mock_repo_rol, mock_hash)
    await use_case.ejecutar(
        ComandoCrearUsuario(email="  UPPER@EJEMPLO.COM  ", nombre="X", apellido="Y", password="Segura1")
    )

    assert capturado["usuario"].email == "upper@ejemplo.com"
