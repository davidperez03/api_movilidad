from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID
from uuid6 import uuid7


def _new_public_id_reg() -> str:
    return f"reg_{uuid7().hex[:27]}"


@dataclass
class RegistroNunc:
    sesion_id: UUID
    placa: str
    nombre_conductor: str
    documento_conductor: str
    id: UUID = field(default_factory=uuid7)
    public_id: str = field(default_factory=_new_public_id_reg)
    numero_secuencial: int = 0
    datos_forenses: dict = field(default_factory=dict)
    creado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    organization_id: UUID | None = None
    creado_por: UUID | None = None

    def __post_init__(self) -> None:
        self.placa = self.placa.upper().strip()
        self.nombre_conductor = self.nombre_conductor.strip()
        self.documento_conductor = self.documento_conductor.strip()
