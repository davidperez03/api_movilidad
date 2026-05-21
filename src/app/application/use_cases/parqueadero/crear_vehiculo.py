import logging
from dataclasses import dataclass
from datetime import date
from uuid import UUID
from app.domain.entities.parqueadero.vehiculo import VehiculoParqueadero, TipoVehiculoParqueadero
from app.domain.ports.outbound.parqueadero.repositorio_vehiculo import RepositorioVehiculo
from app.domain.exceptions import ReglaDeNegocioViolada

logger = logging.getLogger(__name__)


@dataclass
class ComandoCrearVehiculo:
    placa: str
    tipo_vehiculo: TipoVehiculoParqueadero
    marca: str = ""
    modelo: str = ""
    soat_aseguradora: str = ""
    soat_vencimiento: date | None = None
    tecnomecanica_vencimiento: date | None = None
    creado_por: UUID | None = None
    organization_id: UUID | None = None


class CrearVehiculoUseCase:
    def __init__(self, repo: RepositorioVehiculo) -> None:
        self._repo = repo

    async def ejecutar(self, cmd: ComandoCrearVehiculo) -> VehiculoParqueadero:
        placa = cmd.placa.upper().strip()

        if await self._repo.existe_placa(placa, cmd.organization_id):
            raise ReglaDeNegocioViolada(f"Ya existe un vehículo con la placa '{placa}'")

        vehiculo = VehiculoParqueadero(
            placa=placa,
            tipo_vehiculo=cmd.tipo_vehiculo,
            marca=cmd.marca,
            modelo=cmd.modelo,
            soat_aseguradora=cmd.soat_aseguradora,
            soat_vencimiento=cmd.soat_vencimiento,
            tecnomecanica_vencimiento=cmd.tecnomecanica_vencimiento,
            creado_por=cmd.creado_por,
            organization_id=cmd.organization_id,
        )
        vehiculo = await self._repo.guardar(vehiculo)
        logger.info("Vehículo parqueadero creado", extra={"vehiculo_id": str(vehiculo.id), "placa": placa})
        return vehiculo
