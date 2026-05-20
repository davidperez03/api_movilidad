import pytest
from unittest.mock import AsyncMock
from app.application.use_cases.auth.usuarios.autenticar_usuario import (
    AutenticarUsuarioUseCase, ComandoAutenticar,
)
from app.domain.entities.auth.usuario import EstadoUsuario
from app.domain.exceptions import CredencialesInvalidas, UsuarioInactivo


@pytest.mark.asyncio
async def test_login_exitoso(mock_repo_usuario, mock_repo_rol, mock_hash, mock_cache, usuario_activo):
    mock_repo_usuario.buscar_por_email = AsyncMock(return_value=usuario_activo)
    mock_repo_usuario.obtener_hash_password = AsyncMock(return_value="$2b$12$hash")
    mock_repo_usuario.actualizar = AsyncMock(return_value=usuario_activo)
    mock_repo_rol.obtener_permisos_de_usuario = AsyncMock(return_value={"usuarios:leer"})
    mock_hash.verificar = AsyncMock(return_value=True)

    use_case = AutenticarUsuarioUseCase(mock_repo_usuario, mock_repo_rol, mock_hash, mock_cache)
    resultado = await use_case.ejecutar(ComandoAutenticar(email="test@ejemplo.com", password="pass"))

    assert resultado.id == usuario_activo.id
    mock_repo_usuario.actualizar.assert_called_once()


@pytest.mark.asyncio
async def test_login_usuario_inexistente(mock_repo_usuario, mock_repo_rol, mock_hash, mock_cache):
    mock_repo_usuario.buscar_por_email = AsyncMock(return_value=None)
    mock_hash.verificar = AsyncMock(return_value=False)

    use_case = AutenticarUsuarioUseCase(mock_repo_usuario, mock_repo_rol, mock_hash, mock_cache)
    with pytest.raises(CredencialesInvalidas):
        await use_case.ejecutar(ComandoAutenticar(email="no@existe.com", password="x"))

    # Debe haber ejecutado el hash igual (anti-timing)
    mock_hash.verificar.assert_called_once()


@pytest.mark.asyncio
async def test_login_password_incorrecta(mock_repo_usuario, mock_repo_rol, mock_hash, mock_cache, usuario_activo):
    mock_repo_usuario.buscar_por_email = AsyncMock(return_value=usuario_activo)
    mock_repo_usuario.obtener_hash_password = AsyncMock(return_value="$2b$12$hash")
    mock_hash.verificar = AsyncMock(return_value=False)

    use_case = AutenticarUsuarioUseCase(mock_repo_usuario, mock_repo_rol, mock_hash, mock_cache)
    with pytest.raises(CredencialesInvalidas):
        await use_case.ejecutar(ComandoAutenticar(email="test@ejemplo.com", password="mal"))


@pytest.mark.asyncio
async def test_login_usuario_suspendido(mock_repo_usuario, mock_repo_rol, mock_hash, mock_cache, usuario_activo):
    usuario_activo.estado = EstadoUsuario.SUSPENDIDO
    mock_repo_usuario.buscar_por_email = AsyncMock(return_value=usuario_activo)

    use_case = AutenticarUsuarioUseCase(mock_repo_usuario, mock_repo_rol, mock_hash, mock_cache)
    with pytest.raises(UsuarioInactivo):
        await use_case.ejecutar(ComandoAutenticar(email="test@ejemplo.com", password="Segura1"))


@pytest.mark.asyncio
async def test_login_permisos_se_cargan(mock_repo_usuario, mock_repo_rol, mock_hash, mock_cache, usuario_activo):
    mock_repo_usuario.buscar_por_email = AsyncMock(return_value=usuario_activo)
    mock_repo_usuario.obtener_hash_password = AsyncMock(return_value="$2b$12$hash")
    mock_repo_usuario.actualizar = AsyncMock(return_value=usuario_activo)
    mock_repo_rol.obtener_permisos_de_usuario = AsyncMock(return_value={"usuarios:crear", "roles:leer"})
    mock_hash.verificar = AsyncMock(return_value=True)

    use_case = AutenticarUsuarioUseCase(mock_repo_usuario, mock_repo_rol, mock_hash, mock_cache)
    resultado = await use_case.ejecutar(ComandoAutenticar(email="test@ejemplo.com", password="Segura1"))

    assert resultado.tiene_permiso("usuarios:crear")
    assert resultado.tiene_permiso("roles:leer")
    assert not resultado.tiene_permiso("auditoria:leer")
