from abc import ABC, abstractmethod
from uuid import UUID
from typing import Optional
from app.domain.entities.parqueadero.inspeccion import Inspeccion


class FiltrosInspeccion:
    def __init__(
        self,
        vehiculo_id: UUID | None = None,
        personal_id: UUID | None = None,
        es_apto: bool | None = None,
        tamanio: int = 20,
        cursor: str | None = None,
        organization_id: UUID | None = None,
    ):
        self.vehiculo_id = vehiculo_id
        self.personal_id = personal_id
        self.es_apto = es_apto
        self.tamanio = tamanio
        self.cursor = cursor
        self.organization_id = organization_id


class PaginaInspecciones:
    def __init__(self, items: list[Inspeccion], siguiente_cursor: str | None, tamanio: int):
        self.items = items
        self.siguiente_cursor = siguiente_cursor
        self.tamanio = tamanio
        self.tiene_siguiente = siguiente_cursor is not None


class RepositorioInspeccion(ABC):

    @abstractmethod
    async def guardar(self, inspeccion: Inspeccion) -> Inspeccion: ...

    @abstractmethod
    async def actualizar(self, inspeccion: Inspeccion) -> Inspeccion: ...

    @abstractmethod
    async def buscar_por_id(self, id: UUID) -> Optional[Inspeccion]: ...

    @abstractmethod
    async def buscar_por_public_id(self, public_id: str) -> Optional[Inspeccion]: ...

    @abstractmethod
    async def listar(self, filtros: FiltrosInspeccion) -> PaginaInspecciones: ...
