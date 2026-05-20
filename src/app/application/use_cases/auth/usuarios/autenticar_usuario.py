import asyncio
import logging
import time
from dataclasses import dataclass
from app.domain.ports.outbound.auth.repositorio_usuario import RepositorioUsuario
from app.domain.ports.outbound.auth.repositorio_rol import RepositorioRol
from app.domain.ports.outbound.auth.servicio_hash import ServicioHash
from app.domain.ports.outbound.auth.servicio_cache import ServicioCache
from app.domain.entities.auth.usuario import Usuario, EstadoUsuario
from app.domain.exceptions import CredencialesInvalidas, CuentaBloqueada, UsuarioInactivo, VerificacionPendiente
from app.config import config

logger = logging.getLogger(__name__)


@dataclass
class ComandoAutenticar:
    email: str
    password: str


class AutenticarUsuarioUseCase:
    def __init__(
        self,
        repo: RepositorioUsuario,
        repo_rol: RepositorioRol,
        hash_service: ServicioHash,
        cache: ServicioCache,
    ) -> None:
        self._repo = repo
        self._repo_rol = repo_rol
        self._hash = hash_service
        self._cache = cache

    async def ejecutar(self, cmd: ComandoAutenticar) -> Usuario:
        t0 = time.monotonic()
        try:
            return await self._autenticar(cmd)
        except CredencialesInvalidas:
            elapsed = time.monotonic() - t0
            if elapsed < config.LOGIN_MIN_RESPONSE_SECS:
                await asyncio.sleep(config.LOGIN_MIN_RESPONSE_SECS - elapsed)
            raise

    async def _autenticar(self, cmd: ComandoAutenticar) -> Usuario:
        email = cmd.email.lower().strip()

        lockout_key = f"lockout_login:{email}"
        if await self._cache.exists(lockout_key):
            await self._hash.verificar(cmd.password, self._hash.placeholder_hash())
            segundos = await self._cache.ttl(lockout_key)
            raise CuentaBloqueada(max(segundos, 1))

        usuario = await self._repo.buscar_por_email(email)

        if not usuario:
            await self._hash.verificar(cmd.password, self._hash.placeholder_hash())
            await self._registrar_intento_fallido(email)
            logger.warning("Login fallido — email no encontrado", extra={"email": email})
            raise CredencialesInvalidas("Credenciales inválidas")

        if usuario.estado == EstadoUsuario.PENDIENTE_VERIFICACION:
            logger.warning("Login fallido — email sin verificar", extra={"usuario_id": str(usuario.id)})
            raise VerificacionPendiente("Debes verificar tu correo electrónico antes de iniciar sesión")

        if not usuario.puede_autenticarse():
            logger.warning("Login fallido — cuenta inactiva", extra={"usuario_id": str(usuario.id), "estado": usuario.estado.value})
            raise UsuarioInactivo(f"La cuenta está {usuario.estado.value}")

        hash_almacenado = await self._repo.obtener_hash_password(usuario.id)
        if not hash_almacenado or not await self._hash.verificar(cmd.password, hash_almacenado):
            await self._registrar_intento_fallido(email)
            logger.warning("Login fallido — password incorrecto", extra={"usuario_id": str(usuario.id)})
            raise CredencialesInvalidas("Credenciales inválidas")

        await self._cache.delete(f"intentos_login:{email}")

        permisos = await self._repo_rol.obtener_permisos_de_usuario(usuario.id)
        usuario.cargar_permisos(permisos)

        usuario.registrar_login()
        await self._repo.actualizar(usuario)

        await self._cache.delete(f"permisos_usuario:{usuario.id}")

        logger.info("Login exitoso", extra={"usuario_id": str(usuario.id)})
        return usuario

    async def _registrar_intento_fallido(self, email: str) -> None:
        intentos = await self._cache.incr(f"intentos_login:{email}", ttl_segundos=config.LOGIN_LOCKOUT_TTL)
        if intentos >= config.LOGIN_LOCKOUT_MAX_INTENTOS:
            await self._cache.set(f"lockout_login:{email}", "1", config.LOGIN_LOCKOUT_TTL)
            await self._cache.delete(f"intentos_login:{email}")
            logger.warning("Cuenta bloqueada por intentos excesivos", extra={"email": email})
