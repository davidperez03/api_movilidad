import logging
from dataclasses import dataclass
from uuid import UUID
from app.domain.ports.outbound.auth.repositorio_rol import RepositorioRol
from app.domain.entities.auth.rol import Rol
from app.domain.exceptions import RolNoEncontrado, PermisoNoEncontrado

logger = logging.getLogger(__name__)


@dataclass
class ComandoAsignarPermiso:
    rol_id: UUID
    permiso_id: UUID


class AsignarPermisoARolUseCase:
    def __init__(self, repo: RepositorioRol) -> None:
        self._repo = repo

    async def ejecutar(self, cmd: ComandoAsignarPermiso) -> Rol:
        rol = await self._repo.buscar_rol_por_id(cmd.rol_id)
        if not rol:
            raise RolNoEncontrado(f"Rol {cmd.rol_id} no encontrado")

        permisos = await self._repo.listar_permisos()
        permiso = next((p for p in permisos if p.id == cmd.permiso_id), None)
        if not permiso:
            raise PermisoNoEncontrado(f"Permiso {cmd.permiso_id} no encontrado")

        rol.agregar_permiso(permiso)
        rol = await self._repo.actualizar_rol(rol)

        logger.info(
            "Permiso asignado a rol",
            extra={"rol_id": str(cmd.rol_id), "permiso": permiso.clave},
        )
        return rol
