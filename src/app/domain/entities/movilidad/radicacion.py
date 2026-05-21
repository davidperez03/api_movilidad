from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from uuid import UUID
from uuid6 import uuid7


class EstadoRadicacion(str, Enum):
    SIN_ASIGNAR        = "sin_asignar"
    PENDIENTE_RADICAR  = "pendiente_radicar"
    CON_NOVEDADES      = "con_novedades"
    ENVIADO_DEVOLUCION = "enviado_devolucion"
    RECIBIDO           = "recibido"
    REVISADO           = "revisado"
    RADICADO           = "radicado"


TRANSICIONES_RADICACION: dict[EstadoRadicacion, list[EstadoRadicacion]] = {
    EstadoRadicacion.SIN_ASIGNAR:        [EstadoRadicacion.PENDIENTE_RADICAR],
    EstadoRadicacion.PENDIENTE_RADICAR:  [
        EstadoRadicacion.CON_NOVEDADES,
        EstadoRadicacion.ENVIADO_DEVOLUCION,
        EstadoRadicacion.RADICADO,
    ],
    EstadoRadicacion.CON_NOVEDADES:      [EstadoRadicacion.PENDIENTE_RADICAR],
    EstadoRadicacion.ENVIADO_DEVOLUCION: [EstadoRadicacion.RECIBIDO],
    EstadoRadicacion.RECIBIDO:           [EstadoRadicacion.REVISADO],
    EstadoRadicacion.REVISADO:           [EstadoRadicacion.RADICADO],
    EstadoRadicacion.RADICADO:           [],
}


def _new_public_id_rad() -> str:
    return f"rad_{uuid7().hex[:27]}"


@dataclass
class Radicacion:
    cuenta_id: UUID
    id: UUID = field(default_factory=uuid7)
    public_id: str = field(default_factory=_new_public_id_rad)
    organismo_origen_id: UUID | None = None
    empresa_transportadora_id: UUID | None = None
    estado: EstadoRadicacion = EstadoRadicacion.SIN_ASIGNAR
    numero_guia: str = ""
    numero_guia_devolucion: str = ""
    observaciones: str = ""
    radicado_en: datetime | None = None
    vencimiento: date | None = None
    completado_en: datetime | None = None
    version: int = 1
    creado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    actualizado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    organization_id: UUID | None = None
    creado_por: UUID | None = None
    actualizado_por: UUID | None = None

    def cambiar_estado(self, nuevo: EstadoRadicacion, motivo: str = "") -> None:
        from app.domain.exceptions import ReglaDeNegocioViolada
        permitidos = TRANSICIONES_RADICACION.get(self.estado, [])
        if nuevo not in permitidos:
            raise ReglaDeNegocioViolada(
                f"Transición inválida '{self.estado}' → '{nuevo}'. "
                f"Permitidas: {[e.value for e in permitidos]}"
            )
        self.estado = nuevo
        if motivo:
            self.observaciones = motivo
        if nuevo == EstadoRadicacion.RADICADO:
            self.radicado_en = datetime.now(timezone.utc)
        self.actualizado_en = datetime.now(timezone.utc)

    @property
    def esta_activo(self) -> bool:
        return self.estado != EstadoRadicacion.RADICADO

    @property
    def esta_vencido(self) -> bool:
        if self.vencimiento is None:
            return False
        return date.today() > self.vencimiento and self.esta_activo

    def transiciones_disponibles(self) -> list[EstadoRadicacion]:
        return TRANSICIONES_RADICACION.get(self.estado, [])
