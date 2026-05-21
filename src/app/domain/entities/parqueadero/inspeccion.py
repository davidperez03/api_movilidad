from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID
from uuid6 import uuid7


class TurnoInspeccion(str, Enum):
    MANANA = "manana"
    TARDE = "tarde"
    NOCHE = "noche"


class EstadoItem(str, Enum):
    BUENO = "bueno"
    REGULAR = "regular"
    MALO = "malo"
    NA = "na"


def _new_public_id_ins() -> str:
    return f"ins_{uuid7().hex[:27]}"


@dataclass
class ItemInspeccion:
    catalogo_item_id: UUID
    estado: EstadoItem
    observacion: str = ""
    fotos: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if len(self.fotos) > 3:
            from app.domain.exceptions import ReglaDeNegocioViolada
            raise ReglaDeNegocioViolada("Un ítem no puede tener más de 3 fotos")


@dataclass
class Inspeccion:
    vehiculo_id: UUID
    personal_id: UUID
    turno: TurnoInspeccion
    id: UUID = field(default_factory=uuid7)
    public_id: str = field(default_factory=_new_public_id_ins)
    es_apto: bool | None = None
    observaciones_generales: str = ""
    fotos: list[str] = field(default_factory=list)
    items: list[ItemInspeccion] = field(default_factory=list)
    aprobado_por: UUID | None = None
    aprobado_en: datetime | None = None
    creado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    actualizado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    organization_id: UUID | None = None
    creado_por: UUID | None = None

    def __post_init__(self) -> None:
        if len(self.fotos) > 5:
            from app.domain.exceptions import ReglaDeNegocioViolada
            raise ReglaDeNegocioViolada("Una inspección no puede tener más de 5 fotos generales")

    def aprobar(self, aprobado_por: UUID, es_apto: bool) -> None:
        from app.domain.exceptions import ReglaDeNegocioViolada
        if self.aprobado_en is not None:
            raise ReglaDeNegocioViolada("La inspección ya fue aprobada")
        self.es_apto = es_apto
        self.aprobado_por = aprobado_por
        self.aprobado_en = datetime.now(timezone.utc)
        self.actualizado_en = datetime.now(timezone.utc)

    @property
    def esta_aprobada(self) -> bool:
        return self.aprobado_en is not None
