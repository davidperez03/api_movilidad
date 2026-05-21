from abc import ABC, abstractmethod
from uuid import UUID
from typing import Optional
from app.domain.entities.movilidad.radicacion import Radicacion, EstadoRadicacion


class FiltrosRadicacion:
    def __init__(
        self,
        cuenta_id: UUID | None = None,
        traslado_id: UUID | None = None,
        estado: EstadoRadicacion | None = None,
        vencidos: bool | None = None,
        tamanio: int = 20,
        cursor: str | None = None,
        organization_id: UUID | None = None,
    ):
        self.cuenta_id = cuenta_id
        self.traslado_id = traslado_id
        self.estado = estado
        self.vencidos = vencidos
        self.tamanio = tamanio
        self.cursor = cursor
        self.organization_id = organization_id


class PaginaRadicaciones:
    def __init__(self, items: list[Radicacion], siguiente_cursor: str | None, tamanio: int):
        self.items = items
        self.siguiente_cursor = siguiente_cursor
        self.tamanio = tamanio
        self.tiene_siguiente = siguiente_cursor is not None


class RepositorioRadicacion(ABC):

    @abstractmethod
    async def guardar(self, radicacion: Radicacion) -> Radicacion: ...

    @abstractmethod
    async def actualizar(self, radicacion: Radicacion) -> Radicacion: ...

    @abstractmethod
    async def buscar_por_id(self, id: UUID) -> Optional[Radicacion]: ...

    @abstractmethod
    async def buscar_por_public_id(self, public_id: str) -> Optional[Radicacion]: ...

    @abstractmethod
    async def listar(self, filtros: FiltrosRadicacion) -> PaginaRadicaciones: ...

    @abstractmethod
    async def tiene_proceso_activo(self, cuenta_id: UUID) -> bool: ...
