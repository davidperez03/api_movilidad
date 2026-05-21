from abc import ABC, abstractmethod
from uuid import UUID
from typing import Optional
from app.domain.entities.movilidad.traslado import Traslado, EstadoTraslado


class FiltrosTraslado:
    def __init__(
        self,
        cuenta_id: UUID | None = None,
        estado: EstadoTraslado | None = None,
        vencidos: bool | None = None,
        tamanio: int = 20,
        cursor: str | None = None,
        organization_id: UUID | None = None,
    ):
        self.cuenta_id = cuenta_id
        self.estado = estado
        self.vencidos = vencidos
        self.tamanio = tamanio
        self.cursor = cursor
        self.organization_id = organization_id


class PaginaTraslados:
    def __init__(self, items: list[Traslado], siguiente_cursor: str | None, tamanio: int):
        self.items = items
        self.siguiente_cursor = siguiente_cursor
        self.tamanio = tamanio
        self.tiene_siguiente = siguiente_cursor is not None


class RepositorioTraslado(ABC):

    @abstractmethod
    async def guardar(self, traslado: Traslado) -> Traslado: ...

    @abstractmethod
    async def actualizar(self, traslado: Traslado) -> Traslado: ...

    @abstractmethod
    async def buscar_por_id(self, id: UUID) -> Optional[Traslado]: ...

    @abstractmethod
    async def buscar_por_public_id(self, public_id: str) -> Optional[Traslado]: ...

    @abstractmethod
    async def listar(self, filtros: FiltrosTraslado) -> PaginaTraslados: ...

    @abstractmethod
    async def tiene_proceso_activo(self, cuenta_id: UUID) -> bool: ...
