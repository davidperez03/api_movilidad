from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID
from uuid6 import uuid7


def _new_public_id_org() -> str:
    return f"org_{uuid7().hex[:27]}"


@dataclass
class OrganismoTransito:
    nombre: str
    codigo: str
    departamento: str
    municipio: str
    id: UUID = field(default_factory=uuid7)
    public_id: str = field(default_factory=_new_public_id_org)
    activo: bool = True
    creado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    actualizado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    organization_id: UUID | None = None

    def __post_init__(self) -> None:
        self.codigo = self.codigo.upper().strip()
        self.nombre = self.nombre.strip()

    def desactivar(self) -> None:
        self.activo = False
        self.actualizado_en = datetime.now(timezone.utc)
