from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID
from uuid6 import uuid7


def _new_public_id_key() -> str:
    return f"key_{uuid7().hex[:27]}"  # 31 chars — cabe en VARCHAR(35)


@dataclass
class ApiKey:
    nombre: str
    propietario_id: UUID
    permisos: list[str]
    key_prefix: str
    key_hash: str
    id: UUID = field(default_factory=uuid7)
    public_id: str = field(default_factory=_new_public_id_key)
    activa: bool = True
    expira_en: datetime | None = None
    ultimo_uso: datetime | None = None
    creado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def esta_activa(self) -> bool:
        if not self.activa:
            return False
        if self.expira_en and datetime.now(timezone.utc) > self.expira_en:
            return False
        return True

    def registrar_uso(self) -> None:
        self.ultimo_uso = datetime.now(timezone.utc)

    def revocar(self) -> None:
        self.activa = False
