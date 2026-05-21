from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID
from uuid6 import uuid7


class TipoServicio(str, Enum):
    PUBLICO = "PUBLICO"
    PARTICULAR = "PARTICULAR"
    DIPLOMATICO = "DIPLOMATICO"
    OFICIAL = "OFICIAL"


def _new_public_id_cue() -> str:
    return f"cue_{uuid7().hex[:27]}"


@dataclass
class CuentaVehiculo:
    placa: str
    tipo_servicio: TipoServicio
    propietario_nombre: str
    propietario_documento: str
    id: UUID = field(default_factory=uuid7)
    public_id: str = field(default_factory=_new_public_id_cue)
    numero_cuenta: str = ""
    activo: bool = True
    creado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    actualizado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    organization_id: UUID | None = None
    creado_por: UUID | None = None

    def __post_init__(self) -> None:
        self.placa = self.placa.upper().strip()
        self.propietario_nombre = self.propietario_nombre.strip()
        self.propietario_documento = self.propietario_documento.strip()

    def asignar_numero_cuenta(self, numero: str) -> None:
        if self.numero_cuenta:
            from app.domain.exceptions import ReglaDeNegocioViolada
            raise ReglaDeNegocioViolada("La cuenta ya tiene número asignado")
        self.numero_cuenta = numero
        self.actualizado_en = datetime.now(timezone.utc)

    def desactivar(self) -> None:
        self.activo = False
        self.actualizado_en = datetime.now(timezone.utc)
