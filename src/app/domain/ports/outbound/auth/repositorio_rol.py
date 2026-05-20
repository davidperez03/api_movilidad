from abc import ABC, abstractmethod
from uuid import UUID
from typing import Optional
from app.domain.entities.auth.rol import Rol, Permiso, AsignacionRol


class RepositorioRol(ABC):

    @abstractmethod
    async def guardar_rol(self, rol: Rol) -> Rol: ...

    @abstractmethod
    async def actualizar_rol(self, rol: Rol) -> Rol: ...

    @abstractmethod
    async def buscar_rol_por_id(self, id: UUID) -> Optional[Rol]: ...

    @abstractmethod
    async def buscar_rol_por_nombre(self, nombre: str) -> Optional[Rol]: ...

    @abstractmethod
    async def listar_roles(self) -> list[Rol]: ...

    @abstractmethod
    async def eliminar_rol(self, id: UUID) -> None: ...

    @abstractmethod
    async def guardar_permiso(self, permiso: Permiso) -> Permiso: ...

    @abstractmethod
    async def listar_permisos(self) -> list[Permiso]: ...

    @abstractmethod
    async def asignar_rol_a_usuario(self, asignacion: AsignacionRol) -> AsignacionRol: ...

    @abstractmethod
    async def revocar_rol_de_usuario(self, usuario_id: UUID, rol_id: UUID) -> None: ...

    @abstractmethod
    async def obtener_roles_de_usuario(self, usuario_id: UUID) -> list[Rol]: ...

    @abstractmethod
    async def obtener_permisos_de_usuario(self, usuario_id: UUID) -> set[str]: ...

    @abstractmethod
    async def buscar_rol_por_public_id(self, public_id: str) -> Optional[Rol]: ...
