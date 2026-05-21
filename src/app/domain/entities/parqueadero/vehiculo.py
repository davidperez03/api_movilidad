from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from uuid import UUID
from uuid6 import uuid7


class TipoVehiculoParqueadero(str, Enum):
    GRUA_PLATAFORMA = "grua_plataforma"
    CAMIONETA       = "camioneta"
    FURGON          = "furgon"
    OTRO            = "otro"


def _new_public_id_veh() -> str:
    return f"veh_{uuid7().hex[:27]}"


@dataclass
class VehiculoParqueadero:
    placa: str
    tipo_vehiculo: TipoVehiculoParqueadero
    id: UUID = field(default_factory=uuid7)
    public_id: str = field(default_factory=_new_public_id_veh)
    marca: str = ""
    modelo: str = ""
    soat_aseguradora: str = ""
    soat_vencimiento: date | None = None
    tecnomecanica_vencimiento: date | None = None
    activo: bool = True
    version: int = 1
    creado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    actualizado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    organization_id: UUID | None = None
    creado_por: UUID | None = None

    def __post_init__(self) -> None:
        self.placa = self.placa.upper().strip()

    def desactivar(self) -> None:
        self.activo = False
        self.actualizado_en = datetime.now(timezone.utc)
