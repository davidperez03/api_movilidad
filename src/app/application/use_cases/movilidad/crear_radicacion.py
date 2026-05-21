import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from uuid import UUID
from app.domain.entities.movilidad.radicacion import Radicacion
from app.domain.ports.outbound.movilidad.repositorio_cuenta import RepositorioCuenta
from app.domain.ports.outbound.movilidad.repositorio_traslado import RepositorioTraslado
from app.domain.ports.outbound.movilidad.repositorio_radicacion import RepositorioRadicacion
from app.domain.ports.outbound.movilidad.servicio_dias_habiles import ServicioDiasHabilesPort
from app.domain.exceptions import ReglaDeNegocioViolada, EntidadNoEncontrada
from app.domain.entities.movilidad.traslado import EstadoTraslado

logger = logging.getLogger(__name__)

DIAS_HABILES_VENCIMIENTO_RADICACION = 60


@dataclass
class ComandoCrearRadicacion:
    traslado_public_id: str
    organismo_id: UUID
    creado_por: UUID | None = None
    organization_id: UUID | None = None


class CrearRadicacionUseCase:
    def __init__(
        self,
        repo_traslado: RepositorioTraslado,
        repo_radicacion: RepositorioRadicacion,
        svc_dias: ServicioDiasHabilesPort,
    ) -> None:
        self._repo_traslado = repo_traslado
        self._repo_radicacion = repo_radicacion
        self._svc_dias = svc_dias

    async def ejecutar(self, cmd: ComandoCrearRadicacion) -> Radicacion:
        traslado = await self._repo_traslado.buscar_por_public_id(cmd.traslado_public_id)
        if not traslado:
            raise EntidadNoEncontrada("Traslado no encontrado")

        if traslado.estado != EstadoTraslado.APROBADO:
            raise ReglaDeNegocioViolada(
                f"Solo se puede radicar un traslado aprobado. Estado actual: '{traslado.estado.value}'"
            )

        if await self._repo_radicacion.tiene_proceso_activo(traslado.cuenta_id):
            raise ReglaDeNegocioViolada("Ya existe una radicación activa para este vehículo")

        hoy = date.today()
        vence_en_date = await self._svc_dias.sumar_dias_habiles(hoy, DIAS_HABILES_VENCIMIENTO_RADICACION)
        vence_en = datetime(vence_en_date.year, vence_en_date.month, vence_en_date.day, tzinfo=timezone.utc)

        radicacion = Radicacion(
            cuenta_id=traslado.cuenta_id,
            traslado_id=traslado.id,
            organismo_id=cmd.organismo_id,
            vence_en=vence_en,
            creado_por=cmd.creado_por,
            organization_id=cmd.organization_id or traslado.organization_id,
        )

        radicacion = await self._repo_radicacion.guardar(radicacion)
        logger.info("Radicacion creada", extra={"radicacion_id": str(radicacion.id)})
        return radicacion
