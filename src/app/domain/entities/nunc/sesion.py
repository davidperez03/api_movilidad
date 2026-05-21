from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from uuid import UUID
from uuid6 import uuid7

_COLOMBIA_OFFSET = timedelta(hours=-5)


class EstadoSesionNunc(str, Enum):
    ACTIVA   = "activa"
    CERRADA  = "cerrada"
    EXPIRADA = "expirada"


def _midnight_colombia_utc() -> datetime:
    ahora_col = datetime.now(timezone.utc) + _COLOMBIA_OFFSET
    manana_col = ahora_col.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return manana_col - _COLOMBIA_OFFSET


def _new_public_id_nunc() -> str:
    return f"nunc_{uuid7().hex[:25]}"


@dataclass
class SesionNunc:
    nombre_entidad: str
    nombre_perito: str
    departamento: str
    municipio: str
    entidad: str
    unidad: str
    ano: str
    creado_por: UUID
    id: UUID = field(default_factory=uuid7)
    public_id: str = field(default_factory=_new_public_id_nunc)
    codigo_sesion: str = ""
    estado: EstadoSesionNunc = EstadoSesionNunc.ACTIVA
    expiracion: datetime = field(default_factory=_midnight_colombia_utc)
    cerrado_en: datetime | None = None
    creado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    actualizado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    organization_id: UUID | None = None

    @property
    def esta_activa(self) -> bool:
        return self.estado == EstadoSesionNunc.ACTIVA and datetime.now(timezone.utc) < self.expiracion

    def cerrar(self) -> None:
        from app.domain.exceptions import ReglaDeNegocioViolada
        if self.estado != EstadoSesionNunc.ACTIVA:
            raise ReglaDeNegocioViolada("La sesión no está activa")
        self.estado = EstadoSesionNunc.CERRADA
        self.cerrado_en = datetime.now(timezone.utc)
        self.actualizado_en = datetime.now(timezone.utc)
