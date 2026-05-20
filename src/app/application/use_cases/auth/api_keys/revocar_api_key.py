import logging
from dataclasses import dataclass
from uuid import UUID

from app.domain.ports.outbound.auth.repositorio_api_key import RepositorioApiKey
from app.domain.exceptions import EntidadNoEncontrada, PermisoDenegado

logger = logging.getLogger(__name__)


@dataclass
class ComandoRevocarApiKey:
    api_key_id: UUID
    solicitante_id: UUID
    es_admin: bool = False


class RevocarApiKeyUseCase:
    def __init__(self, repo: RepositorioApiKey) -> None:
        self._repo = repo

    async def ejecutar(self, cmd: ComandoRevocarApiKey) -> None:
        api_key = await self._repo.buscar_por_id(cmd.api_key_id)
        if not api_key:
            raise EntidadNoEncontrada(f"API Key {cmd.api_key_id} no encontrada")

        if api_key.propietario_id != cmd.solicitante_id and not cmd.es_admin:
            raise PermisoDenegado("Solo puedes revocar tus propias API Keys")

        api_key.revocar()
        await self._repo.actualizar(api_key)

        logger.info(
            "API Key revocada",
            extra={"api_key_id": str(cmd.api_key_id), "solicitante_id": str(cmd.solicitante_id)},
        )
