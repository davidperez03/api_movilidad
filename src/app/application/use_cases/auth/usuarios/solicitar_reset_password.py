import logging
from dataclasses import dataclass

from app.config import config
from app.domain.ports.outbound.auth.repositorio_usuario import RepositorioUsuario
from app.domain.ports.outbound.auth.servicio_cache import ServicioCache
from app.domain.ports.outbound.auth.servicio_email import ServicioEmail
from app.infrastructure.security.auth.token_service import generar_token_seguro, firmar_token

logger = logging.getLogger(__name__)

_PREFIJO = "reset_password"
_PREFIJO_RATE = "reset_solicitado"


@dataclass
class ComandoSolicitarReset:
    email: str


class SolicitarResetPasswordUseCase:
    def __init__(
        self,
        repo: RepositorioUsuario,
        cache: ServicioCache,
        email_service: ServicioEmail,
    ) -> None:
        self._repo = repo
        self._cache = cache
        self._email = email_service

    async def ejecutar(self, cmd: ComandoSolicitarReset) -> None:
        email = cmd.email.lower().strip()

        rate_key = f"{_PREFIJO_RATE}:{email}"
        if await self._cache.exists(rate_key):
            return

        usuario = await self._repo.buscar_por_email(email)
        if not usuario:
            await self._cache.set(rate_key, "1", config.EMAIL_REENVIO_RATE_TTL)
            return

        token = generar_token_seguro()
        # Almacenar HMAC del token en Redis — mismo patrón que verificación de email
        token_firmado = firmar_token(token)
        await self._cache.set(
            f"{_PREFIJO}:{token_firmado}",
            str(usuario.id),
            config.PASSWORD_RESET_TTL,
        )
        await self._cache.set(rate_key, "1", config.EMAIL_REENVIO_RATE_TTL)

        await self._email.enviar_reset_password(email, usuario.nombre, token)
        logger.info("Reset de password solicitado", extra={"usuario_id": str(usuario.id)})
