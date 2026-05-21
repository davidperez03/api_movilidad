from abc import ABC, abstractmethod
from datetime import date


class ServicioDiasHabilesPort(ABC):

    @abstractmethod
    async def es_dia_habil(self, fecha: date) -> bool: ...

    @abstractmethod
    async def sumar_dias_habiles(self, desde: date, dias: int) -> date: ...

    @abstractmethod
    async def contar_dias_habiles(self, desde: date, hasta: date) -> int: ...
