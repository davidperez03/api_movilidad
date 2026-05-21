from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID
from uuid6 import uuid7


class TipoVehiculoParqueadero(str, Enum):
    CAMION = "camion"
    BUS = "bus"
    BUSETA = "buseta"
    MICROBUS = "microbus"
    CAMIONETA = "camioneta"
    OTRO = "otro"


def _new_public_id_veh() -> str:
    return f"veh_{uuid7().hex[:27]}"


@dataclass
class VehiculoParqueadero:
    placa: str
    tipo: TipoVehiculoParqueadero
    marca: str
    modelo: str
    anio: int
    id: UUID = field(default_factory=uuid7)
    public_id: str = field(default_factory=_new_public_id_veh)
    activo: bool = True
    creado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    actualizado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    organization_id: UUID | None = None

    def __post_init__(self) -> None:
        self.placa = self.placa.upper().strip()
        self.marca = self.marca.strip()
        self.modelo = self.modelo.strip()

    def desactivar(self) -> None:
        self.activo = False
        self.actualizado_en = datetime.now(timezone.utc)
