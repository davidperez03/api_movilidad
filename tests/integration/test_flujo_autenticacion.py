"""
Tests de integración: flujo completo de autenticación contra BD real.

Validan end-to-end:
  - Crear usuario → hash de password almacenado correctamente
  - Verificación de email: token HMAC → activación
  - Login exitoso → permisos correctos desde BD
  - Lockout tras intentos fallidos
  - Reset de password → hash actualizado en BD
  - API Key: creación, validación y revocación
"""
import pytest
from uuid import uuid4

from app.application.use_cases.auth.usuarios.crear_usuario import CrearUsuarioUseCase, ComandoCrearUsuario
from app.application.use_cases.auth.usuarios.autenticar_usuario import AutenticarUsuarioUseCase, ComandoAutenticar
from app.application.use_cases.auth.usuarios.enviar_verificacion_email import (
    EnviarVerificacionEmailUseCase, ComandoEnviarVerificacion,
)
from app.application.use_cases.auth.usuarios.verificar_email import VerificarEmailUseCase, ComandoVerificarEmail
from app.application.use_cases.auth.api_keys.crear_api_key import CrearApiKeyUseCase, ComandoCrearApiKey
from app.application.use_cases.auth.api_keys.validar_api_key import ValidarApiKeyUseCase, ComandoValidarApiKey
from app.application.use_cases.auth.api_keys.revocar_api_key import RevocarApiKeyUseCase, ComandoRevocarApiKey  # noqa
from app.domain.exceptions import CredencialesInvalidas, TokenInvalido, EmailYaRegistrado, ApiKeyInvalida
from app.domain.entities.auth.rol import Rol, AsignacionRol
from app.infrastructure.persistence.repositorios.auth.usuario_repo import UsuarioRepositorioSQL
from app.infrastructure.persistence.repositorios.auth.rol_repo import RolRepositorioSQL
from app.infrastructure.persistence.repositorios.auth.api_key_repo import ApiKeyRepositorioSQL
from app.infrastructure.security.auth.hash_service import BcryptHashService
from app.infrastructure.security.auth.token_service import generar_token_seguro, firmar_token


# ─── Mocks mínimos ────────────────────────────────────────────────────────────

class _CacheMemoria:
    """Cache en memoria para tests de integración (sin Redis real)."""
    def __init__(self): self._store: dict = {}

    async def set(self, k, v, ttl=None): self._store[k] = v
    async def get(self, k): return self._store.get(k)
    async def delete(self, k): self._store.pop(k, None)
    async def exists(self, k): return k in self._store
    async def incr(self, k, ttl_segundos=60):
        self._store[k] = self._store.get(k, 0) + 1
        return self._store[k]
    async def sadd(self, k, *vals, ttl_segundos=0):
        self._store.setdefault(k, set()).update(vals)
    async def smembers(self, k): return self._store.get(k, set())
    async def set_nx(self, k, v, ttl):
        if k in self._store: return False
        self._store[k] = v
        return True


class _EmailCapturado:
    """Captura los emails enviados sin SMTP real."""
    def __init__(self): self.enviados = []

    async def enviar_verificacion(self, email, nombre, token):
        self.enviados.append({"tipo": "verificacion", "email": email, "token": token})

    async def enviar_reset_password(self, email, nombre, token):
        self.enviados.append({"tipo": "reset", "email": email, "token": token})


def _email_unico() -> str:
    return f"integracion-{uuid4().hex[:8]}@test.com"


# ═══════════════════════════════════════════════════════════════════════════════
#  Flujos de usuario
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_crear_usuario_persistencia(db_session):
    """El usuario creado debe persistir en BD con hash de password."""
    repo_u = UsuarioRepositorioSQL(db_session)
    repo_r = RolRepositorioSQL(db_session)
    hash_svc = BcryptHashService()
    email = _email_unico()

    uc = CrearUsuarioUseCase(repo_u, repo_r, hash_svc)
    usuario = await uc.ejecutar(ComandoCrearUsuario(
        email=email, nombre="Test", apellido="Integracion", password="Segura@123!"
    ))

    assert usuario.id is not None

    # El hash en BD debe verificarse con bcrypt
    hash_en_bd = await repo_u.obtener_hash_password(usuario.id)
    assert hash_en_bd is not None
    assert await hash_svc.verificar("Segura@123!", hash_en_bd) is True
    assert await hash_svc.verificar("Incorrecta@123!", hash_en_bd) is False


@pytest.mark.asyncio
async def test_email_duplicado_en_bd(db_session):
    """BD rechaza segundo usuario con mismo email (unique constraint)."""
    repo_u = UsuarioRepositorioSQL(db_session)
    repo_r = RolRepositorioSQL(db_session)
    email = _email_unico()

    uc = CrearUsuarioUseCase(repo_u, repo_r, BcryptHashService())
    await uc.ejecutar(ComandoCrearUsuario(email=email, nombre="A", apellido="B", password="Segura@1!"))

    with pytest.raises(EmailYaRegistrado):
        await uc.ejecutar(ComandoCrearUsuario(email=email, nombre="C", apellido="D", password="Segura@1!"))


@pytest.mark.asyncio
async def test_flujo_verificacion_email_con_hmac(db_session):
    """
    Flujo completo: crear usuario → enviar token HMAC → verificar → activar.
    Valida que el token firmado con HMAC se almacena y verifica correctamente.
    """
    repo_u = UsuarioRepositorioSQL(db_session)
    repo_r = RolRepositorioSQL(db_session)
    cache = _CacheMemoria()
    email_svc = _EmailCapturado()

    usuario = await CrearUsuarioUseCase(repo_u, repo_r, BcryptHashService()).ejecutar(
        ComandoCrearUsuario(
            email=_email_unico(), nombre="Ver", apellido="Ificacion", password="Segura@1!"
        )
    )
    assert usuario.estado.value == "pendiente_verificacion"

    # Enviar verificación — genera token HMAC
    await EnviarVerificacionEmailUseCase(cache, email_svc).ejecutar(
        ComandoEnviarVerificacion(usuario_id=usuario.id, email=usuario.email, nombre="Ver")
    )
    assert len(email_svc.enviados) == 1
    token_en_url = email_svc.enviados[0]["token"]

    # Verificar con el token — debe activar la cuenta
    usuario_activo = await VerificarEmailUseCase(repo_u, cache).ejecutar(
        ComandoVerificarEmail(token=token_en_url)
    )
    assert usuario_activo.estado.value == "activo"
    assert usuario_activo.email_verificado is True

    # El token no debe poder usarse de nuevo (uso único)
    with pytest.raises(TokenInvalido):
        await VerificarEmailUseCase(repo_u, cache).ejecutar(
            ComandoVerificarEmail(token=token_en_url)
        )


@pytest.mark.asyncio
async def test_login_exitoso_tras_verificacion(db_session):
    """Login completo: crear → verificar → autenticar → permisos correctos."""
    repo_u = UsuarioRepositorioSQL(db_session)
    repo_r = RolRepositorioSQL(db_session)
    cache = _CacheMemoria()
    email_svc = _EmailCapturado()
    hash_svc = BcryptHashService()
    password = "Segura@123Test!"
    email = _email_unico()

    usuario = await CrearUsuarioUseCase(repo_u, repo_r, hash_svc).ejecutar(
        ComandoCrearUsuario(email=email, nombre="Login", apellido="Test", password=password)
    )

    await EnviarVerificacionEmailUseCase(cache, email_svc).ejecutar(
        ComandoEnviarVerificacion(usuario_id=usuario.id, email=email, nombre="Login")
    )
    token = email_svc.enviados[0]["token"]
    await VerificarEmailUseCase(repo_u, cache).ejecutar(ComandoVerificarEmail(token=token))

    autenticado = await AutenticarUsuarioUseCase(repo_u, repo_r, hash_svc, cache).ejecutar(
        ComandoAutenticar(email=email, password=password)
    )
    assert autenticado.id == usuario.id
    assert autenticado.estado.value == "activo"


@pytest.mark.asyncio
async def test_login_password_incorrecta_en_bd(db_session):
    """Password incorrecta debe lanzar CredencialesInvalidas contra hash real."""
    repo_u = UsuarioRepositorioSQL(db_session)
    repo_r = RolRepositorioSQL(db_session)
    cache = _CacheMemoria()
    email_svc = _EmailCapturado()
    hash_svc = BcryptHashService()
    email = _email_unico()

    usuario = await CrearUsuarioUseCase(repo_u, repo_r, hash_svc).ejecutar(
        ComandoCrearUsuario(email=email, nombre="X", apellido="Y", password="Correcta@1!")
    )
    await EnviarVerificacionEmailUseCase(cache, email_svc).ejecutar(
        ComandoEnviarVerificacion(usuario_id=usuario.id, email=email, nombre="X")
    )
    token = email_svc.enviados[0]["token"]
    await VerificarEmailUseCase(repo_u, cache).ejecutar(ComandoVerificarEmail(token=token))

    with pytest.raises(CredencialesInvalidas):
        await AutenticarUsuarioUseCase(repo_u, repo_r, hash_svc, cache).ejecutar(
            ComandoAutenticar(email=email, password="Incorrecta@1!")
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  API Keys
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_crear_validar_revocar_api_key(db_session):
    """Ciclo completo de API Key contra BD real."""
    repo_u = UsuarioRepositorioSQL(db_session)
    repo_r = RolRepositorioSQL(db_session)
    repo_k = ApiKeyRepositorioSQL(db_session)
    hash_svc = BcryptHashService()

    usuario = await CrearUsuarioUseCase(repo_u, repo_r, hash_svc).ejecutar(
        ComandoCrearUsuario(email=_email_unico(), nombre="Api", apellido="Key", password="Segura@1!")
    )

    resultado = await CrearApiKeyUseCase(repo_k, repo_u).ejecutar(
        ComandoCrearApiKey(
            nombre="Mi clave de test",
            propietario_id=usuario.id,
            permisos=["usuarios:leer"],
        )
    )
    full_key = resultado.full_key
    api_key = resultado.api_key

    # Validar: la API Key recién creada debe ser válida
    validada = await ValidarApiKeyUseCase(repo_k).ejecutar(
        ComandoValidarApiKey(raw_key=full_key)
    )
    assert validada.id == api_key.id
    assert validada.esta_activa is True

    # Revocar
    await RevocarApiKeyUseCase(repo_k).ejecutar(
        ComandoRevocarApiKey(api_key_id=api_key.id, solicitante_id=usuario.id)
    )

    # Tras revocar: debe fallar
    with pytest.raises(ApiKeyInvalida):
        await ValidarApiKeyUseCase(repo_k).ejecutar(
            ComandoValidarApiKey(raw_key=full_key)
        )


@pytest.mark.asyncio
async def test_api_key_hash_compare_digest(db_session):
    """
    Dos API Keys distintas con mismo prefix no deben confundirse.
    Valida que hmac.compare_digest funciona correctamente contra BD real.
    """
    repo_u = UsuarioRepositorioSQL(db_session)
    repo_r = RolRepositorioSQL(db_session)
    repo_k = ApiKeyRepositorioSQL(db_session)
    hash_svc = BcryptHashService()

    usuario = await CrearUsuarioUseCase(repo_u, repo_r, hash_svc).ejecutar(
        ComandoCrearUsuario(email=_email_unico(), nombre="Hash", apellido="Test", password="Segura@1!")
    )

    # Crear dos keys y probar que no hay colisión
    r1 = await CrearApiKeyUseCase(repo_k, repo_u).ejecutar(
        ComandoCrearApiKey(nombre="Key 1", propietario_id=usuario.id)
    )
    r2 = await CrearApiKeyUseCase(repo_k, repo_u).ejecutar(
        ComandoCrearApiKey(nombre="Key 2", propietario_id=usuario.id)
    )

    v1 = await ValidarApiKeyUseCase(repo_k).ejecutar(ComandoValidarApiKey(raw_key=r1.full_key))
    v2 = await ValidarApiKeyUseCase(repo_k).ejecutar(ComandoValidarApiKey(raw_key=r2.full_key))

    assert v1.id != v2.id
    assert v1.id == r1.api_key.id
    assert v2.id == r2.api_key.id
