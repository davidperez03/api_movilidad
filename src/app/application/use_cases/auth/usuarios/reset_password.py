import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from app.config import config
from app.domain.ports.outbound.auth.repositorio_usuario import RepositorioUsuario
from app.domain.ports.outbound.auth.servicio_cache import ServicioCache
from app.domain.ports.outbound.auth.servicio_hash import ServicioHash
from app.domain.exceptions import TokenInvalido, EntidadNoEncontrada

logger = logging.getLogger(__name__)

_PREFIJO = "reset_password"
_SESION_INVALIDADA_TTL = config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60


@dataclass
class ComandoResetPassword:
    token: str
    nueva_password: str


class ResetPasswordUseCase:
    def __init__(
        self,
        repo: RepositorioUsuario,
        cache: ServicioCache,
        hash_service: ServicioHash,
    ) -> None:
        self._repo = repo
        self._cache = cache
        self._hash = hash_service

    async def ejecutar(self, cmd: ComandoResetPassword) -> None:
        from app.infrastructure.security.auth.token_service import firmar_token, verificar_formato
        if not verificar_formato(cmd.token):
            raise TokenInvalido("El enlace de restablecimiento no es válido o ha expirado")

        token_firmado = firmar_token(cmd.token)
        cache_key = f"{_PREFIJO}:{token_firmado}"
        usuario_id_str = await self._cache.get(cache_key)
        if not usuario_id_str:
            raise TokenInvalido("El enlace de restablecimiento no es válido o ha expirado")

        usuario = await self._repo.buscar_por_id(UUID(usuario_id_str))
        if not usuario:
            raise EntidadNoEncontrada("Usuario no encontrado")

        nuevo_hash = self._hash.hashear(cmd.nueva_password)
        await self._repo.actualizar_password(usuario.id, nuevo_hash)

        await self._cache.delete(cache_key)

        # Invalida tokens JWT activos emitidos antes del cambio de password
        ahora = datetime.now(timezone.utc)
        await self._cache.set(
            f"password_cambiado:{usuario.id}",
            str(ahora.timestamp()),
            _SESION_INVALIDADA_TTL,
        )

        logger.info("Password restablecido", extra={"usuario_id": usuario_id_str})
