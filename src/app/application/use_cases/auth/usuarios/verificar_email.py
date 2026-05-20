import logging
from dataclasses import dataclass
from uuid import UUID

from app.domain.entities.auth.usuario import Usuario
from app.domain.ports.outbound.auth.repositorio_usuario import RepositorioUsuario
from app.domain.ports.outbound.auth.servicio_cache import ServicioCache
from app.domain.exceptions import TokenInvalido, EntidadNoEncontrada
from app.infrastructure.security.auth.token_service import firmar_token, verificar_formato

logger = logging.getLogger(__name__)

_PREFIJO = "email_verificacion"


@dataclass
class ComandoVerificarEmail:
    token: str


class VerificarEmailUseCase:
    def __init__(self, repo: RepositorioUsuario, cache: ServicioCache) -> None:
        self._repo = repo
        self._cache = cache

    async def ejecutar(self, cmd: ComandoVerificarEmail) -> Usuario:
        if not verificar_formato(cmd.token):
            raise TokenInvalido("El enlace de verificación no es válido o ha expirado")

        # Buscar por HMAC del token, no por el token en texto plano
        token_firmado = firmar_token(cmd.token)
        cache_key = f"{_PREFIJO}:{token_firmado}"
        usuario_id_str = await self._cache.get(cache_key)
        if not usuario_id_str:
            raise TokenInvalido("El enlace de verificación no es válido o ha expirado")

        usuario = await self._repo.buscar_por_id(UUID(usuario_id_str))
        if not usuario:
            raise EntidadNoEncontrada("Usuario no encontrado")

        usuario.activar()
        usuario = await self._repo.actualizar(usuario)

        # Eliminar después de uso — garantiza uso único
        await self._cache.delete(cache_key)

        logger.info("Email verificado", extra={"usuario_id": usuario_id_str})
        return usuario
