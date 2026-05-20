from abc import ABC, abstractmethod
from uuid import UUID
from typing import Optional
from app.domain.entities.auth.api_key import ApiKey


class RepositorioApiKey(ABC):

    @abstractmethod
    async def guardar(self, api_key: ApiKey) -> ApiKey: ...

    @abstractmethod
    async def actualizar(self, api_key: ApiKey) -> ApiKey: ...

    @abstractmethod
    async def buscar_por_id(self, id: UUID) -> Optional[ApiKey]: ...

    @abstractmethod
    async def buscar_por_prefix(self, prefix: str) -> list[ApiKey]: ...

    @abstractmethod
    async def listar_por_propietario(self, propietario_id: UUID) -> list[ApiKey]: ...

    @abstractmethod
    async def buscar_por_public_id(self, public_id: str) -> Optional[ApiKey]: ...
