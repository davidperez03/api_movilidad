from abc import ABC, abstractmethod


class ServicioFirma(ABC):

    @abstractmethod
    def firmar(self, payload: str, timestamp: int) -> str:
        """Genera firma HMAC-SHA256 del payload."""
        ...

    @abstractmethod
    def verificar(self, payload: str, timestamp: int, firma_recibida: str) -> bool:
        """Verifica firma y que el timestamp esté dentro de ±300 segundos."""
        ...
