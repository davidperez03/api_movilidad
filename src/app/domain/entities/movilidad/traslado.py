from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from uuid import UUID
from uuid6 import uuid7
from app.domain.exceptions import ReglaDeNegocioViolada


class EstadoTraslado(str, Enum):
    SIN_ASIGNAR       = "sin_asignar"
    REVISADO          = "revisado"
    CON_NOVEDADES     = "con_novedades"
    APROBADO          = "aprobado"
    ENVIADO_ORGANISMO = "enviado_organismo"
    TRASLADADO        = "trasladado"
    DEVUELTO          = "devuelto"


_TERMINALES_TRASLADO = frozenset({EstadoTraslado.TRASLADADO, EstadoTraslado.DEVUELTO})
ESTADOS_TERMINALES_TRASLADO: frozenset[str] = frozenset(e.value for e in _TERMINALES_TRASLADO)

TRANSICIONES_TRASLADO: dict[EstadoTraslado, list[EstadoTraslado]] = {
    EstadoTraslado.SIN_ASIGNAR:       [EstadoTraslado.REVISADO, EstadoTraslado.CON_NOVEDADES, EstadoTraslado.APROBADO],
    EstadoTraslado.REVISADO:          [EstadoTraslado.CON_NOVEDADES, EstadoTraslado.APROBADO, EstadoTraslado.DEVUELTO],
    EstadoTraslado.CON_NOVEDADES:     [EstadoTraslado.REVISADO, EstadoTraslado.APROBADO, EstadoTraslado.DEVUELTO],
    EstadoTraslado.APROBADO:          [EstadoTraslado.ENVIADO_ORGANISMO, EstadoTraslado.DEVUELTO],
    EstadoTraslado.ENVIADO_ORGANISMO: [EstadoTraslado.TRASLADADO, EstadoTraslado.DEVUELTO],
    EstadoTraslado.TRASLADADO:        [],
    EstadoTraslado.DEVUELTO:          [],
}


def _new_public_id_tra() -> str:
    return f"tra_{uuid7().hex[:27]}"


@dataclass
class Traslado:
    cuenta_id: UUID
    id: UUID = field(default_factory=uuid7)
    public_id: str = field(default_factory=_new_public_id_tra)
    organismo_destino_id: UUID | None = None
    empresa_transportadora_id: UUID | None = None
    estado: EstadoTraslado = EstadoTraslado.SIN_ASIGNAR
    numero_guia: str = ""
    observaciones: str = ""
    aprobado_en: datetime | None = None
    vencimiento: date | None = None
    completado_en: datetime | None = None
    version: int = 1
    creado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    actualizado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    organization_id: UUID | None = None
    creado_por: UUID | None = None
    actualizado_por: UUID | None = None

    def cambiar_estado(self, nuevo: EstadoTraslado, motivo: str = "") -> None:
        permitidos = TRANSICIONES_TRASLADO.get(self.estado, [])
        if nuevo not in permitidos:
            raise ReglaDeNegocioViolada(
                f"Transición inválida '{self.estado}' → '{nuevo}'. "
                f"Permitidas: {[e.value for e in permitidos]}"
            )
        self.estado = nuevo
        if motivo:
            self.observaciones = motivo
        self.actualizado_en = datetime.now(timezone.utc)

    @property
    def esta_activo(self) -> bool:
        return self.estado not in _TERMINALES_TRASLADO

    @property
    def esta_vencido(self) -> bool:
        if self.vencimiento is None:
            return False
        return date.today() > self.vencimiento and self.esta_activo

    def transiciones_disponibles(self) -> list[EstadoTraslado]:
        return TRANSICIONES_TRASLADO.get(self.estado, [])
