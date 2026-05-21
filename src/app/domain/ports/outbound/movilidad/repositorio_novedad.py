from abc import ABC, abstractmethod
from uuid import UUID
from typing import Optional
from app.domain.entities.movilidad.novedad import Novedad, EstadoNovedad


class FiltrosNovedad:
    def __init__(
        self,
        cuenta_id: UUID | None = None,
        traslado_id: UUID | None = None,
        radicacion_id: UUID | None = None,
        estado: EstadoNovedad | None = None,
        tamanio: int = 20,
        cursor: str | None = None,
        organization_id: UUID | None = None,
    ):
        self.cuenta_id = cuenta_id
        self.traslado_id = traslado_id
        self.radicacion_id = radicacion_id
        self.estado = estado
        self.tamanio = tamanio
        self.cursor = cursor
        self.organization_id = organization_id


class PaginaNovedades:
    def __init__(self, items: list[Novedad], siguiente_cursor: str | None, tamanio: int):
        self.items = items
        self.siguiente_cursor = siguiente_cursor
        self.tamanio = tamanio
        self.tiene_siguiente = siguiente_cursor is not None


class RepositorioNovedad(ABC):

    @abstractmethod
    async def guardar(self, novedad: Novedad) -> Novedad: ...

    @abstractmethod
    async def actualizar(self, novedad: Novedad) -> Novedad: ...

    @abstractmethod
    async def buscar_por_id(self, id: UUID) -> Optional[Novedad]: ...

    @abstractmethod
    async def buscar_por_public_id(self, public_id: str) -> Optional[Novedad]: ...

    @abstractmethod
    async def listar(self, filtros: FiltrosNovedad) -> PaginaNovedades: ...

    @abstractmethod
    async def novedades_pendientes_cuenta(self, cuenta_id: UUID) -> list[Novedad]: ...
