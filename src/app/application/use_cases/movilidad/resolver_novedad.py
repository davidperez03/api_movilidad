import logging
from dataclasses import dataclass
from uuid import UUID
from app.domain.entities.movilidad.traslado import EstadoTraslado
from app.domain.entities.movilidad.radicacion import EstadoRadicacion
from app.domain.entities.movilidad.novedad import Novedad
from app.domain.ports.outbound.movilidad.repositorio_novedad import RepositorioNovedad
from app.domain.ports.outbound.movilidad.repositorio_traslado import RepositorioTraslado
from app.domain.ports.outbound.movilidad.repositorio_radicacion import RepositorioRadicacion
from app.domain.exceptions import EntidadNoEncontrada, ReglaDeNegocioViolada
from app.application.use_cases.movilidad.cambiar_estado_traslado import (
    CambiarEstadoTrasladoUseCase, ComandoCambiarEstadoTraslado,
)
from app.application.use_cases.movilidad.cambiar_estado_radicacion import (
    CambiarEstadoRadicacionUseCase, ComandoCambiarEstadoRadicacion,
)

logger = logging.getLogger(__name__)


@dataclass
class ComandoResolverNovedad:
    novedad_public_id: str
    solucion: str
    actor_id: UUID


class ResolverNovedadUseCase:
    def __init__(
        self,
        repo_novedad: RepositorioNovedad,
        repo_traslado: RepositorioTraslado,
        repo_radicacion: RepositorioRadicacion,
    ) -> None:
        self._repo_novedad = repo_novedad
        self._repo_traslado = repo_traslado
        self._repo_radicacion = repo_radicacion

    async def _revertir_a_revisado_traslado(self, proceso_id: UUID, actor_id: UUID) -> None:
        proceso = await self._repo_traslado.buscar_por_id(proceso_id)
        if proceso and proceso.estado == EstadoTraslado.CON_NOVEDADES:
            try:
                await CambiarEstadoTrasladoUseCase(self._repo_traslado).ejecutar(
                    ComandoCambiarEstadoTraslado(
                        traslado_public_id=proceso.public_id,
                        nuevo_estado=EstadoTraslado.REVISADO,
                        actor_id=actor_id,
                    )
                )
            except ReglaDeNegocioViolada:
                pass

    async def _revertir_a_revisado_radicacion(self, proceso_id: UUID, actor_id: UUID) -> None:
        proceso = await self._repo_radicacion.buscar_por_id(proceso_id)
        if proceso and proceso.estado == EstadoRadicacion.CON_NOVEDADES:
            try:
                await CambiarEstadoRadicacionUseCase(self._repo_radicacion).ejecutar(
                    ComandoCambiarEstadoRadicacion(
                        radicacion_public_id=proceso.public_id,
                        nuevo_estado=EstadoRadicacion.REVISADO,
                        actor_id=actor_id,
                    )
                )
            except ReglaDeNegocioViolada:
                pass

    async def ejecutar(self, cmd: ComandoResolverNovedad) -> Novedad:
        novedad = await self._repo_novedad.buscar_por_public_id(cmd.novedad_public_id)
        if not novedad:
            raise EntidadNoEncontrada("Novedad no encontrada")

        novedad.resolver(cmd.solucion, cmd.actor_id)
        novedad = await self._repo_novedad.actualizar(novedad)

        pendientes = await self._repo_novedad.novedades_pendientes_cuenta(novedad.proceso_id)
        if not pendientes:
            if novedad.proceso_tipo == "traslado":
                await self._revertir_a_revisado_traslado(novedad.proceso_id, cmd.actor_id)
            elif novedad.proceso_tipo == "radicacion":
                await self._revertir_a_revisado_radicacion(novedad.proceso_id, cmd.actor_id)

        logger.info("Novedad resuelta", extra={"novedad_id": str(novedad.id)})
        return novedad
