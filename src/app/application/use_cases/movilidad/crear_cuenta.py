import logging
from dataclasses import dataclass
from uuid import UUID
from app.domain.entities.movilidad.cuenta import CuentaVehiculo, TipoServicio
from app.domain.ports.outbound.movilidad.repositorio_cuenta import RepositorioCuenta
from app.domain.exceptions import ReglaDeNegocioViolada

logger = logging.getLogger(__name__)


@dataclass
class ComandoCrearCuenta:
    placa: str
    tipo_servicio: TipoServicio
    creado_por: UUID | None = None
    organization_id: UUID | None = None


class CrearCuentaUseCase:
    def __init__(self, repo: RepositorioCuenta) -> None:
        self._repo = repo

    async def ejecutar(self, cmd: ComandoCrearCuenta) -> CuentaVehiculo:
        placa = cmd.placa.upper().strip()

        if await self._repo.existe_placa(placa, cmd.organization_id):
            raise ReglaDeNegocioViolada(f"Ya existe una cuenta para la placa '{placa}'")

        cuenta = CuentaVehiculo(
            placa=placa,
            tipo_servicio=cmd.tipo_servicio,
            creado_por=cmd.creado_por,
            organization_id=cmd.organization_id,
        )
        # El trigger de BD genera numero_cuenta automáticamente al hacer flush
        cuenta = await self._repo.guardar(cuenta)
        logger.info("Cuenta creada", extra={"cuenta_id": str(cuenta.id), "placa": placa})
        return cuenta
