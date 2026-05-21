from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID
from uuid6 import uuid7


class TipoNovedad(str, Enum):
    DOCUMENTOS_FALTANTES   = "documentos_faltantes"
    DOCUMENTOS_INCORRECTOS = "documentos_incorrectos"
    PLACA_INCORRECTA       = "placa_incorrecta"
    OTRO                   = "otro"


class PrioridadNovedad(str, Enum):
    BAJA   = "baja"
    MEDIA  = "media"
    ALTA   = "alta"
    CRITICA = "critica"


class EstadoNovedad(str, Enum):
    PENDIENTE   = "pendiente"
    EN_REVISION = "en_revision"
    RESUELTA    = "resuelta"


def _new_public_id_nov() -> str:
    return f"nov_{uuid7().hex[:27]}"


@dataclass
class Novedad:
    proceso_tipo: str           # 'traslado' | 'radicacion'
    proceso_id: UUID
    tipo_novedad: TipoNovedad
    descripcion: str
    id: UUID = field(default_factory=uuid7)
    public_id: str = field(default_factory=_new_public_id_nov)
    prioridad: PrioridadNovedad = PrioridadNovedad.MEDIA
    estado: EstadoNovedad = EstadoNovedad.PENDIENTE
    solucion: str = ""
    resuelto_por: UUID | None = None
    resuelto_en: datetime | None = None
    creado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    actualizado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    organization_id: UUID | None = None
    creado_por: UUID | None = None

    def __post_init__(self) -> None:
        if self.proceso_tipo not in ("traslado", "radicacion"):
            from app.domain.exceptions import ReglaDeNegocioViolada
            raise ReglaDeNegocioViolada("proceso_tipo debe ser 'traslado' o 'radicacion'")
        self.descripcion = self.descripcion.strip()

    def iniciar_revision(self) -> None:
        from app.domain.exceptions import ReglaDeNegocioViolada
        if self.estado != EstadoNovedad.PENDIENTE:
            raise ReglaDeNegocioViolada("Solo se puede revisar una novedad pendiente")
        self.estado = EstadoNovedad.EN_REVISION
        self.actualizado_en = datetime.now(timezone.utc)

    def resolver(self, solucion: str, resuelto_por: UUID) -> None:
        from app.domain.exceptions import ReglaDeNegocioViolada
        if self.estado == EstadoNovedad.RESUELTA:
            raise ReglaDeNegocioViolada("La novedad ya está resuelta")
        if not solucion.strip():
            raise ReglaDeNegocioViolada("La solución no puede estar vacía")
        self.solucion = solucion.strip()
        self.resuelto_por = resuelto_por
        self.resuelto_en = datetime.now(timezone.utc)
        self.estado = EstadoNovedad.RESUELTA
        self.actualizado_en = datetime.now(timezone.utc)

    @property
    def esta_pendiente(self) -> bool:
        return self.estado != EstadoNovedad.RESUELTA
