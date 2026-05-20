import hashlib
import logging
import secrets
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.domain.entities.auth.api_key import ApiKey
from app.domain.ports.outbound.auth.repositorio_api_key import RepositorioApiKey
from app.domain.ports.outbound.auth.repositorio_usuario import RepositorioUsuario
from app.domain.exceptions import EntidadNoEncontrada

logger = logging.getLogger(__name__)

_PREFIJO_KEY = "gd"


@dataclass
class ComandoCrearApiKey:
    nombre: str
    propietario_id: UUID
    permisos: list[str] = field(default_factory=list)
    expira_en: datetime | None = None


@dataclass
class ResultadoCrearApiKey:
    api_key: ApiKey
    full_key: str


class CrearApiKeyUseCase:
    def __init__(self, repo: RepositorioApiKey, repo_usuario: RepositorioUsuario) -> None:
        self._repo = repo
        self._repo_usuario = repo_usuario

    async def ejecutar(self, cmd: ComandoCrearApiKey) -> ResultadoCrearApiKey:
        usuario = await self._repo_usuario.buscar_por_id(cmd.propietario_id)
        if not usuario:
            raise EntidadNoEncontrada(f"Usuario {cmd.propietario_id} no encontrado")

        raw = secrets.token_urlsafe(32)
        prefix = raw[:8]
        key_hash = hashlib.sha256(raw.encode()).hexdigest()
        full_key = f"{_PREFIJO_KEY}_{raw}"

        api_key = ApiKey(
            nombre=cmd.nombre,
            propietario_id=cmd.propietario_id,
            permisos=cmd.permisos,
            key_prefix=prefix,
            key_hash=key_hash,
            expira_en=cmd.expira_en,
        )
        api_key = await self._repo.guardar(api_key)

        logger.info(
            "API Key creada",
            extra={"api_key_id": str(api_key.id), "propietario_id": str(cmd.propietario_id)},
        )
        return ResultadoCrearApiKey(api_key=api_key, full_key=full_key)
