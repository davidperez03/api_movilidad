import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID
from typing import Optional
from app.domain.entities.parqueadero.inspeccion import Inspeccion
from app.domain.ports.outbound.parqueadero.repositorio_inspeccion import RepositorioInspeccion
from app.domain.exceptions import EntidadNoEncontrada

logger = logging.getLogger(__name__)


@dataclass
class ComandoAprobarInspeccion:
    inspeccion_public_id: str
    es_apto: bool
    firma_operador: str
    firma_inspector: str
    observaciones: Optional[str] = None
    actor_id: Optional[UUID] = None


class AprobarInspeccionUseCase:
    def __init__(self, repo: RepositorioInspeccion) -> None:
        self._repo = repo

    async def ejecutar(self, cmd: ComandoAprobarInspeccion) -> Inspeccion:
        ins = await self._repo.buscar_por_public_id(cmd.inspeccion_public_id)
        if not ins:
            raise EntidadNoEncontrada("Inspección no encontrada")

        ins.es_apto = cmd.es_apto
        ins.firma_operador = cmd.firma_operador
        ins.firma_inspector = cmd.firma_inspector
        if cmd.observaciones:
            ins.observaciones = cmd.observaciones
        ins.actualizado_por = cmd.actor_id
        ins.actualizado_en = datetime.now(timezone.utc)

        ins = await self._repo.actualizar(ins)
        logger.info("Inspección aprobada",
                    extra={"inspeccion_id": str(ins.id), "es_apto": ins.es_apto})
        return ins
