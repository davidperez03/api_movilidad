from dataclasses import dataclass, field
from datetime import date, time, datetime, timezone
from enum import Enum
from uuid import UUID
from uuid6 import uuid7


class TurnoInspeccion(str, Enum):
    DIA   = "dia"
    NOCHE = "noche"


class EstadoItem(str, Enum):
    BUENO    = "bueno"
    REGULAR  = "regular"
    MALO     = "malo"
    NO_APLICA = "no_aplica"


def _new_public_id_ins() -> str:
    return f"ins_{uuid7().hex[:27]}"


@dataclass
class ItemInspeccion:
    inspeccion_id: UUID
    item_catalogo_id: UUID
    codigo: str
    nombre: str
    categoria: str
    estado: EstadoItem
    observaciones: str = ""
    fotos: list[str] = field(default_factory=list)
    subsanado: bool = False
    subsanado_por: UUID | None = None
    subsanado_en: datetime | None = None
    foto_subsanacion: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if len(self.fotos) > 3:
            from app.domain.exceptions import ReglaDeNegocioViolada
            raise ReglaDeNegocioViolada("Un ítem no puede tener más de 3 fotos")


@dataclass
class Inspeccion:
    vehiculo_id: UUID
    operador_id: UUID
    inspector_id: UUID
    fecha: date
    hora: time
    turno: TurnoInspeccion
    id: UUID = field(default_factory=uuid7)
    public_id: str = field(default_factory=_new_public_id_ins)
    codigo: str = ""
    auxiliar_id: UUID | None = None
    es_apto: bool = False
    observaciones: str = ""
    firma_operador: str = ""
    firma_inspector: str = ""
    fotos: list[str] = field(default_factory=list)
    soat_vencimiento_snap: date | None = None
    tecnomecanica_vencimiento_snap: date | None = None
    licencia_vencimiento_snap: date | None = None
    version: int = 1
    creado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    actualizado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    organization_id: UUID | None = None
    creado_por: UUID | None = None
    actualizado_por: UUID | None = None
    items: list[ItemInspeccion] = field(default_factory=list)

    def __post_init__(self) -> None:
        if len(self.fotos) > 5:
            from app.domain.exceptions import ReglaDeNegocioViolada
            raise ReglaDeNegocioViolada("Una inspección no puede tener más de 5 fotos generales")

    def marcar_apto(self, actualizado_por: UUID) -> None:
        self.es_apto = True
        self.actualizado_por = actualizado_por
        self.actualizado_en = datetime.now(timezone.utc)

    def marcar_no_apto(self, actualizado_por: UUID) -> None:
        self.es_apto = False
        self.actualizado_por = actualizado_por
        self.actualizado_en = datetime.now(timezone.utc)
