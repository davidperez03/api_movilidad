from abc import ABC, abstractmethod
from uuid import UUID
from typing import Optional
from app.domain.entities.nunc.sesion import SesionNunc
from app.domain.entities.nunc.registro import RegistroNunc


class FiltrosRegistroNunc:
    def __init__(
        self,
        sesion_id: UUID | None = None,
        placa: str | None = None,
        tamanio: int = 20,
        cursor: str | None = None,
        organization_id: UUID | None = None,
    ):
        self.sesion_id = sesion_id
        self.placa = placa
        self.tamanio = tamanio
        self.cursor = cursor
        self.organization_id = organization_id


class PaginaRegistrosNunc:
    def __init__(self, items: list[RegistroNunc], siguiente_cursor: str | None, tamanio: int):
        self.items = items
        self.siguiente_cursor = siguiente_cursor
        self.tamanio = tamanio
        self.tiene_siguiente = siguiente_cursor is not None


class RepositorioSesionNunc(ABC):

    @abstractmethod
    async def guardar_sesion(self, sesion: SesionNunc) -> SesionNunc: ...

    @abstractmethod
    async def actualizar_sesion(self, sesion: SesionNunc) -> SesionNunc: ...

    @abstractmethod
    async def buscar_sesion_por_codigo(self, codigo: str) -> Optional[SesionNunc]: ...

    @abstractmethod
    async def buscar_sesion_por_public_id(self, public_id: str) -> Optional[SesionNunc]: ...

    @abstractmethod
    async def guardar_registro(self, registro: RegistroNunc) -> RegistroNunc: ...

    @abstractmethod
    async def listar_registros(self, filtros: FiltrosRegistroNunc) -> PaginaRegistrosNunc: ...
