import logging
from dataclasses import dataclass
from datetime import date
from uuid import UUID
from app.domain.entities.movilidad.traslado import Traslado
from app.domain.ports.outbound.movilidad.repositorio_cuenta import RepositorioCuenta
from app.domain.ports.outbound.movilidad.repositorio_traslado import RepositorioTraslado
from app.domain.ports.outbound.movilidad.servicio_dias_habiles import ServicioDiasHabilesPort
from app.domain.exceptions import ReglaDeNegocioViolada, EntidadNoEncontrada

logger = logging.getLogger(__name__)

DIAS_HABILES_VENCIMIENTO_TRASLADO = 60


@dataclass
class ComandoCrearTraslado:
    cuenta_public_id: str
    organismo_destino_id: UUID
    creado_por: UUID | None = None
    organization_id: UUID | None = None


class CrearTrasladoUseCase:
    def __init__(
        self,
        repo_cuenta: RepositorioCuenta,
        repo_traslado: RepositorioTraslado,
        svc_dias: ServicioDiasHabilesPort,
    ) -> None:
        self._repo_cuenta = repo_cuenta
        self._repo_traslado = repo_traslado
        self._svc_dias = svc_dias

    async def ejecutar(self, cmd: ComandoCrearTraslado) -> Traslado:
        cuenta = await self._repo_cuenta.buscar_por_public_id(cmd.cuenta_public_id)
        if not cuenta:
            raise EntidadNoEncontrada("Cuenta no encontrada")
        if not cuenta.activo:
            raise ReglaDeNegocioViolada("La cuenta está inactiva")

        if await self._repo_traslado.tiene_proceso_activo(cuenta.id):
            raise ReglaDeNegocioViolada(
                "La cuenta ya tiene un traslado activo. Solo se permite un proceso a la vez."
            )

        hoy = date.today()
        vence_en_date = await self._svc_dias.sumar_dias_habiles(hoy, DIAS_HABILES_VENCIMIENTO_TRASLADO)

        from datetime import datetime, timezone
        vence_en = datetime(vence_en_date.year, vence_en_date.month, vence_en_date.day, tzinfo=timezone.utc)

        traslado = Traslado(
            cuenta_id=cuenta.id,
            organismo_destino_id=cmd.organismo_destino_id,
            vence_en=vence_en,
            creado_por=cmd.creado_por,
            organization_id=cmd.organization_id or cuenta.organization_id,
        )

        traslado = await self._repo_traslado.guardar(traslado)
        logger.info("Traslado creado", extra={"traslado_id": str(traslado.id), "cuenta_id": str(cuenta.id)})
        return traslado
