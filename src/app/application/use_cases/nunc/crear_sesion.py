import logging
from dataclasses import dataclass
from uuid import UUID
from app.domain.entities.nunc.sesion import SesionNunc
from app.domain.ports.outbound.nunc.repositorio_sesion import RepositorioSesionNunc

logger = logging.getLogger(__name__)


@dataclass
class ComandoCrearSesionNunc:
    creado_por: UUID
    organization_id: UUID | None = None


class CrearSesionNuncUseCase:
    def __init__(self, repo: RepositorioSesionNunc) -> None:
        self._repo = repo

    async def ejecutar(self, cmd: ComandoCrearSesionNunc) -> SesionNunc:
        sesion = SesionNunc(
            creado_por=cmd.creado_por,
            organization_id=cmd.organization_id,
        )
        sesion = await self._repo.guardar_sesion(sesion)
        logger.info("Sesión NUNC creada", extra={"sesion_id": str(sesion.id), "codigo": sesion.codigo})
        return sesion
