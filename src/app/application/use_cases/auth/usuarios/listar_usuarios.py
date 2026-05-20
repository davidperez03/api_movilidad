from uuid import UUID
from app.domain.ports.outbound.auth.repositorio_usuario import RepositorioUsuario, FiltrosUsuario, PaginaUsuarios


class ListarUsuariosUseCase:
    def __init__(self, repo: RepositorioUsuario) -> None:
        self._repo = repo

    async def ejecutar(self, filtros: FiltrosUsuario, organization_id: UUID | None = None) -> PaginaUsuarios:
        filtros.organization_id = organization_id
        return await self._repo.listar(filtros)
