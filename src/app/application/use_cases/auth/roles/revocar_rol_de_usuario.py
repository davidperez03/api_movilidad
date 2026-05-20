import logging
from dataclasses import dataclass
from uuid import UUID
from app.domain.ports.outbound.auth.repositorio_rol import RepositorioRol
from app.domain.ports.outbound.auth.servicio_cache import ServicioCache

logger = logging.getLogger(__name__)


@dataclass
class ComandoRevocarRol:
    usuario_id: UUID
    rol_id: UUID


class RevocarRolDeUsuarioUseCase:
    def __init__(self, repo: RepositorioRol, cache: ServicioCache) -> None:
        self._repo = repo
        self._cache = cache

    async def ejecutar(self, cmd: ComandoRevocarRol) -> None:
        await self._repo.revocar_rol_de_usuario(cmd.usuario_id, cmd.rol_id)
        await self._cache.delete(f"permisos_usuario:{cmd.usuario_id}")
        logger.info(
            "Rol revocado de usuario",
            extra={"usuario_id": str(cmd.usuario_id), "rol_id": str(cmd.rol_id)},
        )
