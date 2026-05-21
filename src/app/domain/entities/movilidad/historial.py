from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID
from uuid6 import uuid7
import hashlib
import json


def _new_public_id_his() -> str:
    return f"his_{uuid7().hex[:27]}"


@dataclass
class HistorialAccion:
    cuenta_id: UUID
    accion: str
    descripcion: str
    id: UUID = field(default_factory=uuid7)
    public_id: str = field(default_factory=_new_public_id_his)
    traslado_id: UUID | None = None
    radicacion_id: UUID | None = None
    novedad_id: UUID | None = None
    realizado_por: UUID | None = None
    metadatos: dict = field(default_factory=dict)
    hash_anterior: str = ""
    hash_registro: str = field(default="", init=False)
    creado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    organization_id: UUID | None = None

    def __post_init__(self) -> None:
        self.hash_registro = self._calcular_hash()

    def _calcular_hash(self) -> str:
        payload = json.dumps({
            "cuenta_id": str(self.cuenta_id),
            "accion": self.accion,
            "descripcion": self.descripcion,
            "hash_anterior": self.hash_anterior,
            "creado_en": self.creado_en.isoformat(),
        }, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()
