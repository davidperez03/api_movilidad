from uuid import UUID
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.entities.auth.api_key import ApiKey
from app.domain.ports.outbound.auth.repositorio_api_key import RepositorioApiKey
from app.infrastructure.persistence.modelos.auth.api_key_modelo import ApiKeyModelo


class ApiKeyRepositorioSQL(RepositorioApiKey):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def guardar(self, api_key: ApiKey) -> ApiKey:
        modelo = ApiKeyModelo(
            id=api_key.id,
            public_id=api_key.public_id,
            nombre=api_key.nombre,
            key_prefix=api_key.key_prefix,
            key_hash=api_key.key_hash,
            propietario_id=api_key.propietario_id,
            permisos=api_key.permisos,
            activa=api_key.activa,
            expira_en=api_key.expira_en,
        )
        self._session.add(modelo)
        await self._session.flush()
        return self._a_entidad(modelo)

    async def actualizar(self, api_key: ApiKey) -> ApiKey:
        modelo = await self._session.get(ApiKeyModelo, api_key.id)
        if not modelo:
            raise ValueError(f"ApiKey {api_key.id} no encontrada")
        modelo.activa = api_key.activa
        modelo.ultimo_uso = api_key.ultimo_uso
        await self._session.flush()
        return self._a_entidad(modelo)

    async def buscar_por_id(self, id: UUID) -> Optional[ApiKey]:
        modelo = await self._session.get(ApiKeyModelo, id)
        return self._a_entidad(modelo) if modelo else None

    async def buscar_por_public_id(self, public_id: str) -> Optional[ApiKey]:
        stmt = select(ApiKeyModelo).where(ApiKeyModelo.public_id == public_id)
        result = await self._session.execute(stmt)
        modelo = result.scalar_one_or_none()
        return self._a_entidad(modelo) if modelo else None

    async def buscar_por_prefix(self, prefix: str) -> list[ApiKey]:
        stmt = select(ApiKeyModelo).where(
            ApiKeyModelo.key_prefix == prefix,
            ApiKeyModelo.activa.is_(True),
        )
        result = await self._session.execute(stmt)
        return [self._a_entidad(m) for m in result.scalars().all()]

    async def listar_por_propietario(
        self,
        propietario_id: UUID,
        organization_id: UUID | None = None,
    ) -> list[ApiKey]:
        stmt = select(ApiKeyModelo).where(ApiKeyModelo.propietario_id == propietario_id)

        if organization_id is not None:
            stmt = stmt.where(ApiKeyModelo.organization_id == organization_id)

        stmt = stmt.order_by(ApiKeyModelo.creado_en.desc())
        result = await self._session.execute(stmt)
        return [self._a_entidad(m) for m in result.scalars().all()]

    @staticmethod
    def _a_entidad(m: ApiKeyModelo) -> ApiKey:
        return ApiKey(
            id=m.id,
            public_id=m.public_id,
            nombre=m.nombre,
            key_prefix=m.key_prefix,
            key_hash=m.key_hash,
            propietario_id=m.propietario_id,
            permisos=list(m.permisos or []),
            activa=m.activa,
            expira_en=m.expira_en,
            ultimo_uso=m.ultimo_uso,
            creado_en=m.creado_en,
        )
