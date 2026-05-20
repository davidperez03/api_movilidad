from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID
from uuid6 import uuid7
from enum import Enum


def _new_public_id_usr() -> str:
    return f"usr_{uuid7().hex[:27]}"  # 31 chars — cabe en VARCHAR(35)


class EstadoUsuario(str, Enum):
    ACTIVO = "activo"
    INACTIVO = "inactivo"
    SUSPENDIDO = "suspendido"
    PENDIENTE_VERIFICACION = "pendiente_verificacion"


@dataclass
class Usuario:
    email: str
    nombre: str
    apellido: str
    id: UUID = field(default_factory=uuid7)
    public_id: str = field(default_factory=_new_public_id_usr)
    estado: EstadoUsuario = EstadoUsuario.PENDIENTE_VERIFICACION
    email_verificado: bool = False
    ultimo_login: datetime | None = None
    creado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    actualizado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    organization_id: UUID | None = None  # Multi-tenancy
    _permisos: set[str] = field(default_factory=set, repr=False, compare=False)

    def __post_init__(self) -> None:
        # Normalización invariante en dominio — ningún path puede crear emails no normalizados
        self.email = self.email.lower().strip()
        self.nombre = self.nombre.strip()
        self.apellido = self.apellido.strip()

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombre} {self.apellido}"

    @property
    def esta_activo(self) -> bool:
        return self.estado == EstadoUsuario.ACTIVO

    def puede_autenticarse(self) -> bool:
        return self.estado == EstadoUsuario.ACTIVO

    def tiene_permiso(self, permiso: str) -> bool:
        return permiso in self._permisos or "*:*" in self._permisos

    def cargar_permisos(self, permisos: set[str]) -> None:
        self._permisos = permisos

    def obtener_permisos(self) -> frozenset[str]:
        return frozenset(self._permisos)

    def activar(self) -> None:
        self.estado = EstadoUsuario.ACTIVO
        self.email_verificado = True
        self._marcar_actualizado()

    def suspender(self) -> None:
        from app.domain.exceptions import ReglaDeNegocioViolada
        if self.estado == EstadoUsuario.SUSPENDIDO:
            raise ReglaDeNegocioViolada("El usuario ya está suspendido")
        self.estado = EstadoUsuario.SUSPENDIDO
        self._marcar_actualizado()

    def desactivar(self) -> None:
        self.estado = EstadoUsuario.INACTIVO
        self._marcar_actualizado()

    def registrar_login(self) -> None:
        self.ultimo_login = datetime.now(timezone.utc)
        self._marcar_actualizado()

    def actualizar_perfil(self, nombre: str | None = None, apellido: str | None = None) -> None:
        if nombre:
            self.nombre = nombre.strip()
        if apellido:
            self.apellido = apellido.strip()
        self._marcar_actualizado()

    def _marcar_actualizado(self) -> None:
        self.actualizado_en = datetime.now(timezone.utc)
