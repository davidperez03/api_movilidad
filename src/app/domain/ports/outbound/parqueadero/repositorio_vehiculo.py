from abc import ABC, abstractmethod
from uuid import UUID
from typing import Optional
from app.domain.entities.parqueadero.vehiculo import VehiculoParqueadero


class FiltrosVehiculo:
    def __init__(
        self,
        placa: str | None = None,
        activo: bool | None = None,
        tamanio: int = 20,
        cursor: str | None = None,
        organization_id: UUID | None = None,
    ):
        self.placa = placa
        self.activo = activo
        self.tamanio = tamanio
        self.cursor = cursor
        self.organization_id = organization_id


class PaginaVehiculos:
    def __init__(self, items: list[VehiculoParqueadero], siguiente_cursor: str | None, tamanio: int):
        self.items = items
        self.siguiente_cursor = siguiente_cursor
        self.tamanio = tamanio
        self.tiene_siguiente = siguiente_cursor is not None


class RepositorioVehiculo(ABC):

    @abstractmethod
    async def guardar(self, vehiculo: VehiculoParqueadero) -> VehiculoParqueadero: ...

    @abstractmethod
    async def actualizar(self, vehiculo: VehiculoParqueadero) -> VehiculoParqueadero: ...

    @abstractmethod
    async def buscar_por_id(self, id: UUID) -> Optional[VehiculoParqueadero]: ...

    @abstractmethod
    async def buscar_por_public_id(self, public_id: str) -> Optional[VehiculoParqueadero]: ...

    @abstractmethod
    async def buscar_por_placa(self, placa: str, organization_id: UUID | None = None) -> Optional[VehiculoParqueadero]: ...

    @abstractmethod
    async def listar(self, filtros: FiltrosVehiculo) -> PaginaVehiculos: ...

    @abstractmethod
    async def existe_placa(self, placa: str, organization_id: UUID | None = None) -> bool: ...
