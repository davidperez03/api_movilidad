from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from uuid import UUID
from uuid6 import uuid7


class TipoFestivo(str, Enum):
    LEY = "ley"
    PUENTE = "puente"
    REGIONAL = "regional"


def _new_public_id_fes() -> str:
    return f"fes_{uuid7().hex[:27]}"


@dataclass
class FestivoColombiano:
    fecha: date
    nombre: str
    tipo: TipoFestivo
    id: UUID = field(default_factory=uuid7)
    public_id: str = field(default_factory=_new_public_id_fes)
    anio: int = field(init=False)

    def __post_init__(self) -> None:
        self.anio = self.fecha.year

    def es_habil(self) -> bool:
        return False
