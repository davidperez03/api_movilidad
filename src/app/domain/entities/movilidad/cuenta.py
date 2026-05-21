from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID
from uuid6 import uuid7


class TipoServicio(str, Enum):
    PARTICULAR = "particular"
    PUBLICO    = "publico"
    OTRO       = "otro"


def _new_public_id_cue() -> str:
    return f"cue_{uuid7().hex[:27]}"


@dataclass
class CuentaVehiculo:
    placa: str
    tipo_servicio: TipoServicio
    id: UUID = field(default_factory=uuid7)
    public_id: str = field(default_factory=_new_public_id_cue)
    numero_cuenta: str = ""
    version: int = 1
    creado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    actualizado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    organization_id: UUID | None = None
    creado_por: UUID | None = None

    def __post_init__(self) -> None:
        self.placa = self.placa.upper().strip()
