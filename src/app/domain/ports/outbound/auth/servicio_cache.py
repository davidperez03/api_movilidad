from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, Set


class ServicioCache(ABC):

    @abstractmethod
    async def set(self, clave: str, valor: str, ttl_segundos: int) -> None: ...

    @abstractmethod
    async def get(self, clave: str) -> Optional[str]: ...

    @abstractmethod
    async def delete(self, clave: str) -> None: ...

    @abstractmethod
    async def exists(self, clave: str) -> bool: ...

    @abstractmethod
    async def incr(self, clave: str, ttl_segundos: int = 60) -> int: ...

    @abstractmethod
    async def sadd(self, clave: str, *valores: str, ttl_segundos: int = 0) -> None: ...

    @abstractmethod
    async def smembers(self, clave: str) -> Set[str]: ...

    @abstractmethod
    async def set_nx(self, clave: str, valor: str, ttl_segundos: int) -> bool: ...

    @abstractmethod
    async def ttl(self, clave: str) -> int: ...
