from abc import ABC, abstractmethod


class ServicioHash(ABC):

    @abstractmethod
    async def hashear(self, texto_plano: str) -> str: ...

    @abstractmethod
    async def verificar(self, texto_plano: str, hash_almacenado: str) -> bool: ...

    @abstractmethod
    def placeholder_hash(self) -> str:
        """Hash válido del algoritmo configurado para usar en timing defense."""
        ...
