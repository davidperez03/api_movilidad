import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid6 import uuid7
from datetime import datetime, timezone, timedelta
from app.application.use_cases.auth.api_keys.crear_api_key import CrearApiKeyUseCase, ComandoCrearApiKey
from app.application.use_cases.auth.api_keys.revocar_api_key import RevocarApiKeyUseCase, ComandoRevocarApiKey
from app.application.use_cases.auth.api_keys.validar_api_key import ValidarApiKeyUseCase, ComandoValidarApiKey
from app.domain.entities.auth.api_key import ApiKey
from app.domain.exceptions import ApiKeyInvalida, EntidadNoEncontrada, PermisoDenegado
from app.domain.entities.auth.usuario import Usuario, EstadoUsuario


def _usuario():
    return Usuario(id=uuid7(), email="x@x.com", nombre="X", apellido="Y", estado=EstadoUsuario.ACTIVO)


def _api_key(activa=True, propietario_id=None):
    return ApiKey(
        id=uuid7(),
        nombre="test-key",
        key_prefix="sk_te",
        key_hash="hash",
        propietario_id=propietario_id or uuid7(),
        permisos=["usuarios:leer"],
        activa=activa,
    )


@pytest.mark.asyncio
async def test_crear_api_key_exitoso(mock_repo_api_key, mock_repo_usuario):
    usuario = _usuario()
    mock_repo_usuario.buscar_por_id = AsyncMock(return_value=usuario)
    mock_repo_api_key.guardar = AsyncMock(side_effect=lambda key: key)

    resultado = await CrearApiKeyUseCase(mock_repo_api_key, mock_repo_usuario).ejecutar(
        ComandoCrearApiKey(
            nombre="mi-key",
            propietario_id=usuario.id,
            permisos=["usuarios:leer"],
        )
    )

    assert resultado.full_key.startswith("gd_")
    assert resultado.api_key.nombre == "mi-key"
    mock_repo_api_key.guardar.assert_called_once()


@pytest.mark.asyncio
async def test_crear_api_key_usuario_inexistente(mock_repo_api_key, mock_repo_usuario):
    mock_repo_usuario.buscar_por_id = AsyncMock(return_value=None)

    with pytest.raises(EntidadNoEncontrada):
        await CrearApiKeyUseCase(mock_repo_api_key, mock_repo_usuario).ejecutar(
            ComandoCrearApiKey(nombre="key", propietario_id=uuid7(), permisos=[])
        )


@pytest.mark.asyncio
async def test_revocar_api_key_propietario(mock_repo_api_key):
    propietario_id = uuid7()
    key = _api_key(propietario_id=propietario_id)
    mock_repo_api_key.buscar_por_id = AsyncMock(return_value=key)
    mock_repo_api_key.actualizar = AsyncMock()

    await RevocarApiKeyUseCase(mock_repo_api_key).ejecutar(
        ComandoRevocarApiKey(api_key_id=key.id, solicitante_id=propietario_id, es_admin=False)
    )

    mock_repo_api_key.actualizar.assert_called_once()


@pytest.mark.asyncio
async def test_revocar_api_key_sin_permiso(mock_repo_api_key):
    key = _api_key(propietario_id=uuid7())
    mock_repo_api_key.buscar_por_id = AsyncMock(return_value=key)

    with pytest.raises(PermisoDenegado):
        await RevocarApiKeyUseCase(mock_repo_api_key).ejecutar(
            ComandoRevocarApiKey(api_key_id=key.id, solicitante_id=uuid7(), es_admin=False)
        )


@pytest.mark.asyncio
async def test_validar_api_key_invalida(mock_repo_api_key):
    mock_repo_api_key.buscar_por_hash = AsyncMock(return_value=None)

    with pytest.raises(ApiKeyInvalida):
        await ValidarApiKeyUseCase(mock_repo_api_key).ejecutar(
            ComandoValidarApiKey(raw_key="sk_invalida_clave")
        )


@pytest.mark.asyncio
async def test_validar_api_key_revocada(mock_repo_api_key):
    key = _api_key(activa=False)
    mock_repo_api_key.buscar_por_hash = AsyncMock(return_value=key)

    with pytest.raises(ApiKeyInvalida):
        await ValidarApiKeyUseCase(mock_repo_api_key).ejecutar(
            ComandoValidarApiKey(raw_key="sk_test_cualquiercosa")
        )
