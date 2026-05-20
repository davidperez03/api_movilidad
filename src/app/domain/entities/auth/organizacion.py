from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID
from uuid6 import uuid7


def _new_public_id_org() -> str:
    return f"org_{uuid7().hex[:27]}"  # 31 chars — cabe en VARCHAR(40)


@dataclass
class Organizacion:
    nombre: str
    slug: str                # Identificador URL-friendly único (ej. "acme-corp")
    id: UUID = field(default_factory=uuid7)
    public_id: str = field(default_factory=_new_public_id_org)
    activa: bool = True
    plan: str = "free"       # free | pro | enterprise
    creado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    actualizado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        self.nombre = self.nombre.strip()
        self.slug = self.slug.lower().strip().replace(" ", "-")

    def desactivar(self) -> None:
        from app.domain.exceptions import ReglaDeNegocioViolada
        if not self.activa:
            raise ReglaDeNegocioViolada("La organización ya está inactiva")
        self.activa = False
        self._marcar_actualizado()

    def _marcar_actualizado(self) -> None:
        self.actualizado_en = datetime.now(timezone.utc)
