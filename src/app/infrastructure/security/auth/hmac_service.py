import hashlib
import hmac
import time
from app.config import config
from app.domain.ports.outbound.auth.servicio_firma import ServicioFirma
from app.domain.exceptions import FirmaInvalida


class HmacService(ServicioFirma):

    def _secreto(self) -> bytes:
        if not config.HMAC_SIGNING_SECRET:
            raise FirmaInvalida("HMAC_SIGNING_SECRET no está configurado")
        return config.HMAC_SIGNING_SECRET.get_secret_value().encode("utf-8")

    def firmar(self, payload: str, timestamp: int) -> str:
        mensaje = f"{timestamp}.{payload}".encode("utf-8")
        firma = hmac.new(self._secreto(), mensaje, hashlib.sha256).hexdigest()
        return f"sha256={firma}"

    def verificar(self, payload: str, timestamp: int, firma_recibida: str) -> bool:
        ahora = int(time.time())
        if abs(ahora - timestamp) > config.HMAC_REPLAY_WINDOW_SECONDS:
            raise FirmaInvalida(f"Timestamp fuera de ventana (±{config.HMAC_REPLAY_WINDOW_SECONDS}s)")

        firma_esperada = self.firmar(payload, timestamp)

        # Comparación segura (previene timing attacks)
        if not hmac.compare_digest(
            firma_esperada.encode("utf-8"),
            firma_recibida.encode("utf-8"),
        ):
            raise FirmaInvalida("Firma HMAC inválida")

        return True
