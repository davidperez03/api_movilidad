from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from uuid import UUID
from uuid6 import uuid7


@dataclass
class DatosPersonal:
    """Extensión del perfil de un usuario con datos específicos de parqueadero."""
    perfil_id: UUID                    # referencias usuarios.id
    id: UUID = field(default_factory=uuid7)
    licencia_numero: str = ""
    licencia_categoria: str = ""
    licencia_vencimiento: date | None = None
    documento_tipo: str = ""
    documento_numero: str = ""
    telefono: str = ""
    contacto_emergencia_nombre: str = ""
    contacto_emergencia_telefono: str = ""
    notas: str = ""
    creado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    actualizado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    organization_id: UUID | None = None

    @property
    def licencia_vigente(self) -> bool:
        if not self.licencia_vencimiento:
            return False
        return self.licencia_vencimiento >= date.today()
