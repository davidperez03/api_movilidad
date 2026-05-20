import logging
from dataclasses import dataclass
from uuid import UUID

from app.config import config
from app.domain.ports.outbound.auth.servicio_cache import ServicioCache
from app.domain.ports.outbound.auth.servicio_email import ServicioEmail
from app.infrastructure.security.auth.token_service import generar_token_seguro, firmar_token

logger = logging.getLogger(__name__)

_PREFIJO = "email_verificacion"
_PREFIJO_RATE = "reenvio_verificacion"


@dataclass
class ComandoEnviarVerificacion:
    usuario_id: UUID
    email: str
    nombre: str


class EnviarVerificacionEmailUseCase:
    def __init__(self, cache: ServicioCache, email_service: ServicioEmail) -> None:
        self._cache = cache
        self._email = email_service

    async def ejecutar(self, cmd: ComandoEnviarVerificacion) -> None:
        rate_key = f"{_PREFIJO_RATE}:{cmd.email}"
        if await self._cache.exists(rate_key):
            logger.warning("Reenvío de verificación limitado", extra={"email": cmd.email})
            return

        token = generar_token_seguro()
        # Almacenar HMAC del token en Redis — el token original solo viaja en la URL.
        # Si Redis es comprometido, el atacante obtiene HMACs, no los tokens reales.
        token_firmado = firmar_token(token)
        await self._cache.set(
            f"{_PREFIJO}:{token_firmado}",
            str(cmd.usuario_id),
            config.EMAIL_VERIFICATION_TTL,
        )
        await self._cache.set(rate_key, "1", config.EMAIL_REENVIO_RATE_TTL)

        await self._email.enviar_verificacion(cmd.email, cmd.nombre, token)
        logger.info("Email de verificación enviado", extra={"usuario_id": str(cmd.usuario_id)})
