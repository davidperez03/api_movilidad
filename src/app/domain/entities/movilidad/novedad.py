from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID
from uuid6 import uuid7


class TipoNovedad(str, Enum):
    DOCUMENTAL = "documental"
    TECNICA = "tecnica"
    JURIDICA = "juridica"
    FISCAL = "fiscal"
    OTRO = "otro"


class PrioridadNovedad(str, Enum):
    BAJA = "baja"
    MEDIA = "media"
    ALTA = "alta"
    CRITICA = "critica"


class EstadoNovedad(str, Enum):
    ABIERTA = "abierta"
    EN_PROCESO = "en_proceso"
    RESUELTA = "resuelta"
    CERRADA = "cerrada"


def _new_public_id_nov() -> str:
    return f"nov_{uuid7().hex[:27]}"


@dataclass
class Novedad:
    cuenta_id: UUID
    tipo: TipoNovedad
    descripcion: str
    id: UUID = field(default_factory=uuid7)
    public_id: str = field(default_factory=_new_public_id_nov)
    prioridad: PrioridadNovedad = PrioridadNovedad.MEDIA
    estado: EstadoNovedad = EstadoNovedad.ABIERTA
    traslado_id: UUID | None = None
    radicacion_id: UUID | None = None
    resolucion: str = ""
    resuelto_en: datetime | None = None
    creado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    actualizado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    organization_id: UUID | None = None
    creado_por: UUID | None = None
    asignado_a: UUID | None = None

    def __post_init__(self) -> None:
        self.descripcion = self.descripcion.strip()

    def iniciar(self) -> None:
        from app.domain.exceptions import ReglaDeNegocioViolada
        if self.estado != EstadoNovedad.ABIERTA:
            raise ReglaDeNegocioViolada("Solo se puede iniciar una novedad abierta")
        self.estado = EstadoNovedad.EN_PROCESO
        self.actualizado_en = datetime.now(timezone.utc)

    def resolver(self, resolucion: str) -> None:
        from app.domain.exceptions import ReglaDeNegocioViolada
        if self.estado not in (EstadoNovedad.ABIERTA, EstadoNovedad.EN_PROCESO):
            raise ReglaDeNegocioViolada("Solo se puede resolver una novedad abierta o en proceso")
        if not resolucion.strip():
            raise ReglaDeNegocioViolada("La resolución no puede estar vacía")
        self.resolucion = resolucion.strip()
        self.estado = EstadoNovedad.RESUELTA
        self.resuelto_en = datetime.now(timezone.utc)
        self.actualizado_en = datetime.now(timezone.utc)

    def cerrar(self) -> None:
        from app.domain.exceptions import ReglaDeNegocioViolada
        if self.estado != EstadoNovedad.RESUELTA:
            raise ReglaDeNegocioViolada("Solo se puede cerrar una novedad resuelta")
        self.estado = EstadoNovedad.CERRADA
        self.actualizado_en = datetime.now(timezone.utc)

    @property
    def esta_pendiente(self) -> bool:
        return self.estado in (EstadoNovedad.ABIERTA, EstadoNovedad.EN_PROCESO)
