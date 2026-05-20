from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID
from uuid6 import uuid7


def _new_public_id_rol() -> str:
    return f"rol_{uuid7().hex[:27]}"  # 31 chars — cabe en VARCHAR(35)


@dataclass
class Permiso:
    recurso: str
    accion: str
    descripcion: str = ""
    id: UUID = field(default_factory=uuid7)

    @property
    def clave(self) -> str:
        return f"{self.recurso}:{self.accion}"

    def __hash__(self) -> int:
        return hash(self.clave)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Permiso):
            return False
        return self.clave == other.clave


@dataclass
class Rol:
    nombre: str
    descripcion: str
    es_sistema: bool = False
    id: UUID = field(default_factory=uuid7)
    public_id: str = field(default_factory=_new_public_id_rol)
    permisos: set[Permiso] = field(default_factory=set)
    creado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    actualizado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def agregar_permiso(self, permiso: Permiso) -> None:
        self.permisos.add(permiso)
        self._marcar_actualizado()

    def remover_permiso(self, permiso_id: UUID) -> None:
        self.permisos = {p for p in self.permisos if p.id != permiso_id}
        self._marcar_actualizado()

    def obtener_claves_permisos(self) -> set[str]:
        return {p.clave for p in self.permisos}

    def _marcar_actualizado(self) -> None:
        self.actualizado_en = datetime.now(timezone.utc)


@dataclass
class AsignacionRol:
    usuario_id: UUID
    rol_id: UUID
    id: UUID = field(default_factory=uuid7)
    vigente_hasta: datetime | None = None
    asignado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    asignado_por_id: UUID | None = None

    @property
    def esta_vigente(self) -> bool:
        if self.vigente_hasta is None:
            return True
        return datetime.now(timezone.utc) < self.vigente_hasta
