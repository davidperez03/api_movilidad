import hashlib
import hmac
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.config import config
from app.domain.entities.auth.api_key import ApiKey
from app.domain.ports.outbound.auth.repositorio_api_key import RepositorioApiKey
from app.domain.exceptions import ApiKeyInvalida

logger = logging.getLogger(__name__)

_PREFIJO_KEY = "gd_"


@dataclass
class ComandoValidarApiKey:
    raw_key: str


class ValidarApiKeyUseCase:
    def __init__(self, repo: RepositorioApiKey) -> None:
        self._repo = repo

    async def ejecutar(self, cmd: ComandoValidarApiKey) -> ApiKey:
        if not cmd.raw_key.startswith(_PREFIJO_KEY):
            raise ApiKeyInvalida("Formato de API Key inválido")

        token = cmd.raw_key[len(_PREFIJO_KEY):]
        if len(token) < 8:
            raise ApiKeyInvalida("Formato de API Key inválido")

        prefix = token[:8]
        expected_hash = hashlib.sha256(token.encode()).hexdigest()

        candidatos = await self._repo.buscar_por_prefix(prefix)
        for candidato in candidatos:
            # Comparación en tiempo constante — previene timing attacks
            if hmac.compare_digest(candidato.key_hash, expected_hash):
                if not candidato.esta_activa:
                    raise ApiKeyInvalida("API Key revocada o expirada")
                ahora = datetime.now(timezone.utc)
                if candidato.ultimo_uso is None or (ahora - candidato.ultimo_uso) > timedelta(seconds=config.API_KEY_USO_THROTTLE_SECONDS):
                    candidato.registrar_uso()
                    await self._repo.actualizar(candidato)
                return candidato

        raise ApiKeyInvalida("API Key inválida")
