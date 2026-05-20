"""Background tasks compartidos para operaciones de usuario."""
import logging
from uuid import UUID

logger = logging.getLogger(__name__)


async def enviar_verificacion_email_bg(usuario_id: UUID, email: str, nombre: str) -> None:
    from app.application.use_cases.auth.usuarios.enviar_verificacion_email import (
        EnviarVerificacionEmailUseCase, ComandoEnviarVerificacion,
    )
    from app.infrastructure.messaging.smtp_email_service import SmtpEmailService
    from app.infrastructure.cache.redis_service import RedisService
    try:
        await EnviarVerificacionEmailUseCase(RedisService(), SmtpEmailService()).ejecutar(
            ComandoEnviarVerificacion(usuario_id=usuario_id, email=email, nombre=nombre)
        )
    except Exception:
        logger.error("Error enviando email de verificación", exc_info=True)
