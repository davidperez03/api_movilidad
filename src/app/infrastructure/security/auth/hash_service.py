import asyncio
import bcrypt
from app.config import config
from app.domain.ports.outbound.auth.servicio_hash import ServicioHash

# Generado una sola vez al importar el módulo (≈300ms, solo en startup).
# Usar bcrypt.gensalt() garantiza que el hash sea siempre válido,
# sin depender de un string hardcodeado que podría quedar malformado.
_BCRYPT_PLACEHOLDER: str = bcrypt.hashpw(
    b"__placeholder_timing_defense__",
    bcrypt.gensalt(rounds=12),
).decode("utf-8")


class BcryptHashService(ServicioHash):

    async def hashear(self, texto_plano: str) -> str:
        loop = asyncio.get_running_loop()
        rounds = config.BCRYPT_ROUNDS
        encoded = texto_plano.encode("utf-8")
        return await loop.run_in_executor(
            None, lambda: bcrypt.hashpw(encoded, bcrypt.gensalt(rounds=rounds)).decode("utf-8")
        )

    async def verificar(self, texto_plano: str, hash_almacenado: str) -> bool:
        loop = asyncio.get_running_loop()
        encoded = texto_plano.encode("utf-8")
        hash_enc = hash_almacenado.encode("utf-8")
        try:
            return await loop.run_in_executor(
                None, lambda: bcrypt.checkpw(encoded, hash_enc)
            )
        except (ValueError, TypeError):
            return False

    def placeholder_hash(self) -> str:
        return _BCRYPT_PLACEHOLDER
