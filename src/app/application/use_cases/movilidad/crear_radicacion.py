import logging
from dataclasses import dataclass
from uuid import UUID
from app.domain.entities.movilidad.radicacion import Radicacion
from app.domain.ports.outbound.movilidad.repositorio_cuenta import RepositorioCuenta
from app.domain.ports.outbound.movilidad.repositorio_radicacion import RepositorioRadicacion
from app.domain.ports.outbound.movilidad.repositorio_traslado import RepositorioTraslado
from app.domain.entities.movilidad.traslado import EstadoTraslado
from app.domain.exceptions import ReglaDeNegocioViolada, EntidadNoEncontrada

logger = logging.getLogger(__name__)


@dataclass
class ComandoCrearRadicacion:
    cuenta_public_id: str
    organismo_origen_id: UUID | None = None
    empresa_transportadora_id: UUID | None = None
    creado_por: UUID | None = None
    organization_id: UUID | None = None


class CrearRadicacionUseCase:
    def __init__(
        self,
        repo_cuenta: RepositorioCuenta,
        repo_traslado: RepositorioTraslado,
        repo_radicacion: RepositorioRadicacion,
    ) -> None:
        self._repo_cuenta = repo_cuenta
        self._repo_traslado = repo_traslado
        self._repo_radicacion = repo_radicacion

    async def ejecutar(self, cmd: ComandoCrearRadicacion) -> Radicacion:
        cuenta = await self._repo_cuenta.buscar_por_public_id(cmd.cuenta_public_id)
        if not cuenta:
            raise EntidadNoEncontrada("Cuenta no encontrada")

        # Debe haber un traslado aprobado para poder radicar
        from app.domain.ports.outbound.movilidad.repositorio_traslado import FiltrosTraslado
        pagina = await self._repo_traslado.listar(
            FiltrosTraslado(cuenta_id=cuenta.id, estado=EstadoTraslado.APROBADO, tamanio=1)
        )
        if not pagina.items:
            raise ReglaDeNegocioViolada(
                "No existe un traslado aprobado para esta cuenta. Apruebe el traslado primero."
            )

        if await self._repo_radicacion.tiene_proceso_activo(cuenta.id):
            raise ReglaDeNegocioViolada("Ya existe una radicación activa para esta cuenta.")

        radicacion = Radicacion(
            cuenta_id=cuenta.id,
            organismo_origen_id=cmd.organismo_origen_id,
            empresa_transportadora_id=cmd.empresa_transportadora_id,
            creado_por=cmd.creado_por,
            organization_id=cmd.organization_id or cuenta.organization_id,
        )
        # El trigger BD asigna vencimiento (60 días hábiles desde INSERT)
        radicacion = await self._repo_radicacion.guardar(radicacion)
        logger.info("Radicacion creada", extra={"radicacion_id": str(radicacion.id)})
        return radicacion
