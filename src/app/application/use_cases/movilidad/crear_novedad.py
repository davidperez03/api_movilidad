import logging
from dataclasses import dataclass
from uuid import UUID
from typing import Optional
from app.domain.entities.movilidad.novedad import Novedad, TipoNovedad, PrioridadNovedad
from app.domain.entities.movilidad.traslado import EstadoTraslado, _TERMINALES_TRASLADO
from app.domain.entities.movilidad.radicacion import EstadoRadicacion, _TERMINALES_RADICACION
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
class ComandoCrearNovedad:
    proceso_tipo: str          # 'traslado' | 'radicacion'
    proceso_public_id: str
    tipo_novedad: TipoNovedad
    descripcion: str
    prioridad: PrioridadNovedad = PrioridadNovedad.MEDIA
    creado_por: Optional[UUID] = None
    organization_id: Optional[UUID] = None


class CrearNovedadUseCase:
    def __init__(
        self,
        repo_novedad: RepositorioNovedad,
        repo_traslado: RepositorioTraslado,
        repo_radicacion: RepositorioRadicacion,
    ) -> None:
        self._repo_novedad = repo_novedad
        self._repo_traslado = repo_traslado
        self._repo_radicacion = repo_radicacion

    async def _cambiar_a_con_novedades_traslado(self, public_id: str, actor_id: Optional[UUID]) -> None:
        try:
            await CambiarEstadoTrasladoUseCase(self._repo_traslado).ejecutar(
                ComandoCambiarEstadoTraslado(
                    traslado_public_id=public_id,
                    nuevo_estado=EstadoTraslado.CON_NOVEDADES,
                    actor_id=actor_id,
                )
            )
        except ReglaDeNegocioViolada:
            pass

    async def _cambiar_a_con_novedades_radicacion(self, public_id: str, actor_id: Optional[UUID]) -> None:
        try:
            await CambiarEstadoRadicacionUseCase(self._repo_radicacion).ejecutar(
                ComandoCambiarEstadoRadicacion(
                    radicacion_public_id=public_id,
                    nuevo_estado=EstadoRadicacion.CON_NOVEDADES,
                    actor_id=actor_id,
                )
            )
        except ReglaDeNegocioViolada:
            pass

    async def ejecutar(self, cmd: ComandoCrearNovedad) -> Novedad:
        if cmd.proceso_tipo == "traslado":
            proceso = await self._repo_traslado.buscar_por_public_id(cmd.proceso_public_id)
            if not proceso:
                raise EntidadNoEncontrada("Traslado no encontrado")
            if proceso.estado in _TERMINALES_TRASLADO:
                raise ReglaDeNegocioViolada("No se puede agregar una novedad a un proceso terminado")

            novedad = Novedad(
                proceso_tipo="traslado",
                proceso_id=proceso.id,
                tipo_novedad=cmd.tipo_novedad,
                descripcion=cmd.descripcion,
                prioridad=cmd.prioridad,
                creado_por=cmd.creado_por,
                organization_id=cmd.organization_id,
            )
            novedad = await self._repo_novedad.guardar(novedad)
            await self._cambiar_a_con_novedades_traslado(cmd.proceso_public_id, cmd.creado_por)

        elif cmd.proceso_tipo == "radicacion":
            proceso = await self._repo_radicacion.buscar_por_public_id(cmd.proceso_public_id)
            if not proceso:
                raise EntidadNoEncontrada("Radicación no encontrada")
            if proceso.estado in _TERMINALES_RADICACION:
                raise ReglaDeNegocioViolada("No se puede agregar una novedad a un proceso terminado")

            novedad = Novedad(
                proceso_tipo="radicacion",
                proceso_id=proceso.id,
                tipo_novedad=cmd.tipo_novedad,
                descripcion=cmd.descripcion,
                prioridad=cmd.prioridad,
                creado_por=cmd.creado_por,
                organization_id=cmd.organization_id,
            )
            novedad = await self._repo_novedad.guardar(novedad)
            await self._cambiar_a_con_novedades_radicacion(cmd.proceso_public_id, cmd.creado_por)

        else:
            raise ReglaDeNegocioViolada("proceso_tipo debe ser 'traslado' o 'radicacion'")

        logger.info("Novedad creada", extra={"novedad_id": str(novedad.id), "proceso_tipo": cmd.proceso_tipo})
        return novedad
