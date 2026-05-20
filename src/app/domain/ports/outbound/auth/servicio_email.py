from __future__ import annotations
from abc import ABC, abstractmethod


class ServicioEmail(ABC):

    @abstractmethod
    async def enviar_verificacion(self, destinatario: str, nombre: str, token: str) -> None: ...

    @abstractmethod
    async def enviar_reset_password(self, destinatario: str, nombre: str, token: str) -> None: ...
