import logging
from dataclasses import dataclass
from app.domain.entities.auth.rol import Rol
from app.domain.ports.outbound.auth.repositorio_rol import RepositorioRol
from app.domain.exceptions import ReglaDeNegocioViolada

logger = logging.getLogger(__name__)


@dataclass
class ComandoCrearRol:
    nombre: str
    descripcion: str


class CrearRolUseCase:
    def __init__(self, repo: RepositorioRol) -> None:
        self._repo = repo

    async def ejecutar(self, cmd: ComandoCrearRol) -> Rol:
        existente = await self._repo.buscar_rol_por_nombre(cmd.nombre)
        if existente:
            raise ReglaDeNegocioViolada(f"Ya existe un rol con nombre '{cmd.nombre}'")

        rol = Rol(nombre=cmd.nombre.lower().strip(), descripcion=cmd.descripcion)
        rol = await self._repo.guardar_rol(rol)
        logger.info("Rol creado", extra={"rol_id": str(rol.id), "nombre": rol.nombre})
        return rol
