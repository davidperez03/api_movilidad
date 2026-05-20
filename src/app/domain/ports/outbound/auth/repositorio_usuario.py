from abc import ABC, abstractmethod
from uuid import UUID
from typing import Optional
from app.domain.entities.auth.usuario import Usuario, EstadoUsuario


class FiltrosUsuario:
    def __init__(
        self,
        estado: EstadoUsuario | None = None,
        busqueda: str | None = None,
        tamanio: int = 20,
        cursor: str | None = None,
        organization_id: "UUID | None" = None,
    ):
        self.estado = estado
        self.busqueda = busqueda
        self.tamanio = tamanio
        self.cursor = cursor
        self.organization_id = organization_id


class PaginaUsuarios:
    def __init__(self, items: list[Usuario], siguiente_cursor: str | None, tamanio: int):
        self.items = items
        self.siguiente_cursor = siguiente_cursor
        self.tamanio = tamanio
        self.tiene_siguiente = siguiente_cursor is not None


class RepositorioUsuario(ABC):

    @abstractmethod
    async def guardar(self, usuario: Usuario, hash_password: str) -> Usuario: ...

    @abstractmethod
    async def actualizar(self, usuario: Usuario) -> Usuario: ...

    @abstractmethod
    async def buscar_por_id(self, id: UUID) -> Optional[Usuario]: ...

    @abstractmethod
    async def buscar_por_email(self, email: str) -> Optional[Usuario]: ...

    @abstractmethod
    async def obtener_hash_password(self, usuario_id: UUID) -> Optional[str]: ...

    @abstractmethod
    async def actualizar_password(self, usuario_id: UUID, nuevo_hash: str) -> None: ...

    @abstractmethod
    async def listar(self, filtros: FiltrosUsuario) -> PaginaUsuarios: ...

    @abstractmethod
    async def existe_email(self, email: str) -> bool: ...

    @abstractmethod
    async def buscar_por_public_id(self, public_id: str) -> Optional[Usuario]: ...
