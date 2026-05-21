import logging
from dataclasses import dataclass, field
from datetime import date, time
from uuid import UUID
from app.domain.entities.parqueadero.inspeccion import Inspeccion, TurnoInspeccion
from app.domain.ports.outbound.parqueadero.repositorio_vehiculo import RepositorioVehiculo
from app.domain.ports.outbound.parqueadero.repositorio_inspeccion import RepositorioInspeccion
from app.domain.exceptions import EntidadNoEncontrada

logger = logging.getLogger(__name__)


@dataclass
class ComandoCrearInspeccion:
    vehiculo_public_id: str
    operador_id: UUID
    inspector_id: UUID
    fecha: date
    hora: time
    turno: TurnoInspeccion
    auxiliar_id: UUID | None = None
    observaciones: str = ""
    fotos: list[str] = field(default_factory=list)
    soat_vencimiento_snap: date | None = None
    tecnomecanica_vencimiento_snap: date | None = None
    licencia_vencimiento_snap: date | None = None
    creado_por: UUID | None = None
    organization_id: UUID | None = None


class CrearInspeccionUseCase:
    def __init__(self, repo_vehiculo: RepositorioVehiculo, repo_inspeccion: RepositorioInspeccion) -> None:
        self._repo_vehiculo = repo_vehiculo
        self._repo_inspeccion = repo_inspeccion

    async def ejecutar(self, cmd: ComandoCrearInspeccion) -> Inspeccion:
        vehiculo = await self._repo_vehiculo.buscar_por_public_id(cmd.vehiculo_public_id)
        if not vehiculo:
            raise EntidadNoEncontrada("Vehículo no encontrado")

        inspeccion = Inspeccion(
            vehiculo_id=vehiculo.id,
            operador_id=cmd.operador_id,
            inspector_id=cmd.inspector_id,
            auxiliar_id=cmd.auxiliar_id,
            fecha=cmd.fecha,
            hora=cmd.hora,
            turno=cmd.turno,
            observaciones=cmd.observaciones,
            fotos=cmd.fotos,
            soat_vencimiento_snap=cmd.soat_vencimiento_snap or vehiculo.soat_vencimiento,
            tecnomecanica_vencimiento_snap=cmd.tecnomecanica_vencimiento_snap or vehiculo.tecnomecanica_vencimiento,
            licencia_vencimiento_snap=cmd.licencia_vencimiento_snap,
            creado_por=cmd.creado_por,
            organization_id=cmd.organization_id or vehiculo.organization_id,
        )
        inspeccion = await self._repo_inspeccion.guardar(inspeccion)
        logger.info("Inspección creada", extra={"inspeccion_id": str(inspeccion.id)})
        return inspeccion
