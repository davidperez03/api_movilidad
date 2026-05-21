from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from uuid import UUID
from uuid6 import uuid7


def _new_public_id_per() -> str:
    return f"per_{uuid7().hex[:27]}"


@dataclass
class DatosPersonal:
    nombre: str
    documento: str
    cargo: str
    id: UUID = field(default_factory=uuid7)
    public_id: str = field(default_factory=_new_public_id_per)
    numero_licencia: str = ""
    categoria_licencia: str = ""
    vencimiento_licencia: date | None = None
    contacto_emergencia_nombre: str = ""
    contacto_emergencia_telefono: str = ""
    activo: bool = True
    creado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    actualizado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    organization_id: UUID | None = None

    def __post_init__(self) -> None:
        self.nombre = self.nombre.strip()
        self.documento = self.documento.strip()
        self.cargo = self.cargo.strip()

    @property
    def licencia_vigente(self) -> bool:
        if not self.vencimiento_licencia:
            return False
        return self.vencimiento_licencia >= date.today()

    def desactivar(self) -> None:
        self.activo = False
        self.actualizado_en = datetime.now(timezone.utc)
