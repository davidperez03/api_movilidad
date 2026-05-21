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
    numero_guia: str = ""
    numero_guia_devolucion: str = ""
    organismo_origen_id: UUID | None = None
    empresa_transportadora_id: UUID | None = None
    actor_id: UUID | None = None


class CambiarEstadoRadicacionUseCase:
    def __init__(self, repo: RepositorioRadicacion) -> None:
        self._repo = repo

    async def ejecutar(self, cmd: ComandoCambiarEstadoRadicacion) -> Radicacion:
        radicacion = await self._repo.buscar_por_public_id(cmd.radicacion_public_id)
        if not radicacion:
            raise EntidadNoEncontrada("Radicación no encontrada")

        radicacion.cambiar_estado(cmd.nuevo_estado, cmd.motivo)

        if cmd.numero_guia:
            radicacion.numero_guia = cmd.numero_guia
        if cmd.numero_guia_devolucion:
            radicacion.numero_guia_devolucion = cmd.numero_guia_devolucion
        if cmd.organismo_origen_id:
            radicacion.organismo_origen_id = cmd.organismo_origen_id
        if cmd.empresa_transportadora_id:
            radicacion.empresa_transportadora_id = cmd.empresa_transportadora_id
        radicacion.actualizado_por = cmd.actor_id

        radicacion = await self._repo.actualizar(radicacion)
        logger.info("Estado radicacion cambiado",
                    extra={"radicacion_id": str(radicacion.id), "estado": radicacion.estado.value})
        return radicacion
