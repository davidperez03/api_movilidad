import logging
from dataclasses import dataclass, field
from uuid import UUID
from app.domain.entities.movilidad.traslado import Traslado, EstadoTraslado
from app.domain.ports.outbound.movilidad.repositorio_traslado import RepositorioTraslado
from app.domain.exceptions import EntidadNoEncontrada

logger = logging.getLogger(__name__)


@dataclass
class ComandoCambiarEstadoTraslado:
    traslado_public_id: str
    nuevo_estado: EstadoTraslado
    motivo: str = ""
    numero_guia: str = ""
    organismo_destino_id: UUID | None = None
    empresa_transportadora_id: UUID | None = None
    actor_id: UUID | None = None


class CambiarEstadoTrasladoUseCase:
    def __init__(self, repo: RepositorioTraslado) -> None:
        self._repo = repo

    async def ejecutar(self, cmd: ComandoCambiarEstadoTraslado) -> Traslado:
        traslado = await self._repo.buscar_por_public_id(cmd.traslado_public_id)
        if not traslado:
            raise EntidadNoEncontrada("Traslado no encontrado")

        traslado.cambiar_estado(cmd.nuevo_estado, cmd.motivo)

        if cmd.numero_guia:
            traslado.numero_guia = cmd.numero_guia
        if cmd.organismo_destino_id:
            traslado.organismo_destino_id = cmd.organismo_destino_id
        if cmd.empresa_transportadora_id:
            traslado.empresa_transportadora_id = cmd.empresa_transportadora_id
        traslado.actualizado_por = cmd.actor_id

        traslado = await self._repo.actualizar(traslado)
        logger.info("Estado traslado cambiado",
                    extra={"traslado_id": str(traslado.id), "estado": traslado.estado.value})
        return traslado
