import logging
from dataclasses import dataclass
from uuid import UUID
from app.domain.entities.movilidad.traslado import Traslado
from app.domain.ports.outbound.movilidad.repositorio_cuenta import RepositorioCuenta
from app.domain.ports.outbound.movilidad.repositorio_traslado import RepositorioTraslado
from app.domain.ports.outbound.movilidad.repositorio_radicacion import RepositorioRadicacion
from app.domain.exceptions import ReglaDeNegocioViolada, EntidadNoEncontrada

logger = logging.getLogger(__name__)


@dataclass
class ComandoCrearTraslado:
    cuenta_public_id: str
    organismo_destino_id: UUID
    empresa_transportadora_id: UUID | None = None
    creado_por: UUID | None = None
    organization_id: UUID | None = None


class CrearTrasladoUseCase:
    def __init__(
        self,
        repo_cuenta: RepositorioCuenta,
        repo_traslado: RepositorioTraslado,
        repo_radicacion: RepositorioRadicacion,
    ) -> None:
        self._repo_cuenta = repo_cuenta
        self._repo_traslado = repo_traslado
        self._repo_radicacion = repo_radicacion

    async def ejecutar(self, cmd: ComandoCrearTraslado) -> Traslado:
        cuenta = await self._repo_cuenta.buscar_por_public_id(cmd.cuenta_public_id)
        if not cuenta:
            raise EntidadNoEncontrada("Cuenta no encontrada")

        if await self._repo_traslado.tiene_proceso_activo(cuenta.id):
            raise ReglaDeNegocioViolada(
                "La cuenta ya tiene un proceso activo. Solo se permite uno a la vez."
            )

        # Validar secuencia: si el último proceso completado fue un traslado,
        # debe radicarse primero antes de otro traslado.
        ultimo_traslado = await self._repo_traslado.ultimo_completado(cuenta.id)
        if ultimo_traslado:
            ultima_rad = await self._repo_radicacion.ultimo_completado(cuenta.id)
            if ultima_rad is None or (
                ultimo_traslado.actualizado_en and ultima_rad.actualizado_en and
                ultimo_traslado.actualizado_en > ultima_rad.actualizado_en
            ):
                raise ReglaDeNegocioViolada(
                    "Este vehículo fue trasladado previamente. Debe ser radicado primero antes de otro traslado."
                )

        traslado = Traslado(
            cuenta_id=cuenta.id,
            organismo_destino_id=cmd.organismo_destino_id,
            empresa_transportadora_id=cmd.empresa_transportadora_id,
            creado_por=cmd.creado_por,
            organization_id=cmd.organization_id or cuenta.organization_id,
        )
        # El trigger BD asigna vencimiento (60 días hábiles) al aprobar
        traslado = await self._repo_traslado.guardar(traslado)
        logger.info("Traslado creado", extra={"traslado_id": str(traslado.id)})
        return traslado
