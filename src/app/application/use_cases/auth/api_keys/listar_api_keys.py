from dataclasses import dataclass
from uuid import UUID

from app.domain.entities.auth.api_key import ApiKey
from app.domain.ports.outbound.auth.repositorio_api_key import RepositorioApiKey


@dataclass
class ComandoListarApiKeys:
    propietario_id: UUID


class ListarApiKeysUseCase:
    def __init__(self, repo: RepositorioApiKey) -> None:
        self._repo = repo

    async def ejecutar(self, cmd: ComandoListarApiKeys) -> list[ApiKey]:
        return await self._repo.listar_por_propietario(cmd.propietario_id)
