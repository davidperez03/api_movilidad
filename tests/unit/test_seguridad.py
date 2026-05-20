"""Tests de seguridad: autenticación, autorización, rate limiting y tokens."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid6 import uuid7
from app.domain.entities.auth.usuario import Usuario, EstadoUsuario
from app.domain.exceptions import (
    CredencialesInvalidas, CuentaBloqueada, TokenInvalido,
)
from app.application.use_cases.auth.usuarios.autenticar_usuario import (
    AutenticarUsuarioUseCase, ComandoAutenticar,
)
from app.application.use_cases.auth.usuarios.verificar_email import (
    VerificarEmailUseCase, ComandoVerificarEmail,
)
from app.application.use_cases.auth.usuarios.reset_password import (
    ResetPasswordUseCase, ComandoResetPassword,
)
from app.application.use_cases.auth.api_keys.validar_api_key import (
    ValidarApiKeyUseCase, ComandoValidarApiKey,
)
from app.infrastructure.security.auth.token_service import generar_token_seguro, firmar_token


# ---------------------------------------------------------------------------
# Autenticación — timing attacks
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_bloqueado_ejecuta_hash_de_todas_formas(
    mock_repo_usuario, mock_repo_rol, mock_hash, mock_cache
):
    """Cuenta bloqueada: siempre ejecutar hash para evitar timing attack."""
    mock_cache.exists = AsyncMock(return_value=True)
    mock_cache.ttl = AsyncMock(return_value=540)

    uc = AutenticarUsuarioUseCase(mock_repo_usuario, mock_repo_rol, mock_hash, mock_cache)
    with pytest.raises(CuentaBloqueada):
        await uc.ejecutar(ComandoAutenticar(email="victim@example.com", password="cualquiera"))

    mock_hash.verificar.assert_called_once()


@pytest.mark.asyncio
async def test_login_bloqueado_informa_tiempo_restante(
    mock_repo_usuario, mock_repo_rol, mock_hash, mock_cache
):
    """Cuenta bloqueada informa los segundos restantes para reintentar."""
    mock_cache.exists = AsyncMock(return_value=True)
    mock_cache.ttl = AsyncMock(return_value=540)

    uc = AutenticarUsuarioUseCase(mock_repo_usuario, mock_repo_rol, mock_hash, mock_cache)
    with pytest.raises(CuentaBloqueada) as exc_info:
        await uc.ejecutar(ComandoAutenticar(email="victim@example.com", password="x"))

    assert exc_info.value.segundos_restantes == 540


@pytest.mark.asyncio
async def test_login_usuario_inexistente_ejecuta_hash(
    mock_repo_usuario, mock_repo_rol, mock_hash, mock_cache
):
    """Email inexistente: siempre ejecutar hash — previene user enumeration por timing."""
    mock_repo_usuario.buscar_por_email = AsyncMock(return_value=None)
    mock_hash.verificar = AsyncMock(return_value=False)

    uc = AutenticarUsuarioUseCase(mock_repo_usuario, mock_repo_rol, mock_hash, mock_cache)
    with pytest.raises(CredencialesInvalidas):
        await uc.ejecutar(ComandoAutenticar(email="noexiste@example.com", password="x"))

    mock_hash.verificar.assert_called_once()


# ---------------------------------------------------------------------------
# Tokens de email — HMAC signing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_verificar_email_token_invalido_no_consulta_redis(mock_repo_usuario, mock_cache):
    """Token con formato inválido rechazado sin consultar Redis."""
    uc = VerificarEmailUseCase(mock_repo_usuario, mock_cache)
    with pytest.raises(TokenInvalido):
        await uc.ejecutar(ComandoVerificarEmail(token="corto"))

    mock_cache.get.assert_not_called()


@pytest.mark.asyncio
async def test_verificar_email_busca_por_hmac_no_por_token_plano(mock_repo_usuario, mock_cache):
    """El cache de Redis se consulta por HMAC del token, no por el token en texto plano."""
    mock_cache.get = AsyncMock(return_value=None)

    token = generar_token_seguro()
    uc = VerificarEmailUseCase(mock_repo_usuario, mock_cache)
    with pytest.raises(TokenInvalido):
        await uc.ejecutar(ComandoVerificarEmail(token=token))

    call_args = mock_cache.get.call_args[0][0]
    assert token not in call_args, "Redis no debe recibir el token en texto plano como clave"
    assert "email_verificacion:" in call_args


@pytest.mark.asyncio
async def test_verificar_email_token_de_uso_unico(mock_repo_usuario, mock_cache):
    """Después de verificar, el token se elimina de Redis — no se puede reusar."""
    usuario_id = str(uuid7())
    usuario_mock = MagicMock()
    usuario_mock.activar = MagicMock()

    token = generar_token_seguro()
    firma = firmar_token(token)

    mock_cache.get = AsyncMock(return_value=usuario_id)
    mock_cache.delete = AsyncMock()
    mock_repo_usuario.buscar_por_id = AsyncMock(return_value=usuario_mock)
    mock_repo_usuario.actualizar = AsyncMock(return_value=usuario_mock)

    uc = VerificarEmailUseCase(mock_repo_usuario, mock_cache)
    await uc.ejecutar(ComandoVerificarEmail(token=token))

    delete_key = mock_cache.delete.call_args[0][0]
    assert firma in delete_key, "El token HMAC debe eliminarse de Redis tras el uso"


# ---------------------------------------------------------------------------
# Reset de contraseña — tokens HMAC
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reset_password_token_invalido_rechazado(mock_repo_usuario, mock_cache, mock_hash):
    """Token de reset con formato inválido rechazado inmediatamente."""
    uc = ResetPasswordUseCase(mock_repo_usuario, mock_cache, mock_hash)
    with pytest.raises(TokenInvalido):
        await uc.ejecutar(ComandoResetPassword(token="mal", nueva_password="Nueva@123!"))


# ---------------------------------------------------------------------------
# API Keys — hmac.compare_digest
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_validar_api_key_prefijo_incorrecto(mock_repo_api_key):
    """API Key con prefijo incorrecto rechazada sin consultar BD."""
    from app.domain.exceptions import ApiKeyInvalida
    uc = ValidarApiKeyUseCase(mock_repo_api_key)
    with pytest.raises(ApiKeyInvalida):
        await uc.ejecutar(ComandoValidarApiKey(raw_key="sk_live_abc123"))

    mock_repo_api_key.buscar_por_prefix.assert_not_called()


@pytest.mark.asyncio
async def test_validar_api_key_inexistente(mock_repo_api_key):
    """API Key con prefijo correcto pero no registrada — rechazada."""
    from app.domain.exceptions import ApiKeyInvalida
    import secrets
    mock_repo_api_key.buscar_por_prefix = AsyncMock(return_value=[])
    uc = ValidarApiKeyUseCase(mock_repo_api_key)
    raw_key = f"gd_{secrets.token_urlsafe(32)}"
    with pytest.raises(ApiKeyInvalida):
        await uc.ejecutar(ComandoValidarApiKey(raw_key=raw_key))


# ---------------------------------------------------------------------------
# Normalización de email en dominio
# ---------------------------------------------------------------------------

def test_usuario_normaliza_email_en_creacion():
    """El email siempre se normaliza a minúsculas en la entidad de dominio."""
    u = Usuario(email="TEST@EJEMPLO.COM  ", nombre="Juan", apellido="Pérez")
    assert u.email == "test@ejemplo.com"


def test_usuario_normaliza_nombre_apellido():
    u = Usuario(email="a@b.com", nombre="  Juan  ", apellido="  Pérez  ")
    assert u.nombre == "Juan"
    assert u.apellido == "Pérez"
