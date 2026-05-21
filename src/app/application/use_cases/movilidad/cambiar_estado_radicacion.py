import logging
from dataclasses import dataclass
from uuid import UUID
from app.domain.entities.movilidad.radicacion import Radicacion, EstadoRadicacion
from app.domain.ports.outbound.movilidad.repositorio_radicacion import RepositorioRadicacion
from app.domain.exceptions import EntidadNoEncontrada

logger = logging.getLogger(__name__)


@dataclass
class ComandoCambiarEstadoRadicacion:
    radicacion_public_id: str
    nuevo_estado: EstadoRadicacion
    motivo: str = ""
    numero_radicado: str = ""
    actor_id: UUID | None = None


class CambiarEstadoRadicacionUseCase:
    def __init__(self, repo: RepositorioRadicacion) -> None:
        self._repo = repo

    async def ejecutar(self, cmd: ComandoCambiarEstadoRadicacion) -> Radicacion:
        radicacion = await self._repo.buscar_por_public_id(cmd.radicacion_public_id)
        if not radicacion:
            raise EntidadNoEncontrada("Radicación no encontrada")

        radicacion.cambiar_estado(cmd.nuevo_estado, cmd.motivo)

        if cmd.numero_radicado and cmd.nuevo_estado == EstadoRadicacion.RADICADO:
            radicacion.asignar_numero_radicado(cmd.numero_radicado)

        radicacion = await self._repo.actualizar(radicacion)

        logger.info(
            "Estado radicacion cambiado",
            extra={"radicacion_id": str(radicacion.id), "estado": radicacion.estado.value},
        )
        return radicacion
