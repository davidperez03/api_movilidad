from uuid import UUID
from typing import Optional
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.entities.movilidad.organismo import OrganismoTransito
from app.infrastructure.persistence.modelos.movilidad.organismo_modelo import OrganismoTransitoModelo


class OrganismoRepositorioSQL:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def guardar(self, org: OrganismoTransito) -> OrganismoTransito:
        modelo = OrganismoTransitoModelo(
            id=org.id,
            public_id=org.public_id,
            nombre=org.nombre,
            tipo=getattr(org, "tipo", ""),
            municipio=org.municipio,
            departamento=org.departamento,
            activo=org.activo,
            creado_en=org.creado_en,
            actualizado_en=org.actualizado_en,
        )
        self._session.add(modelo)
        await self._session.flush()
        return self._a_entidad(modelo)

    async def buscar_por_id(self, id: UUID) -> Optional[OrganismoTransito]:
        m = await self._session.get(OrganismoTransitoModelo, id)
        return self._a_entidad(m) if m else None

    async def buscar_por_public_id(self, public_id: str) -> Optional[OrganismoTransito]:
        result = await self._session.execute(
            select(OrganismoTransitoModelo).where(OrganismoTransitoModelo.public_id == public_id)
        )
        m = result.scalar_one_or_none()
        return self._a_entidad(m) if m else None

    async def listar(
        self,
        q: str | None = None,
        departamento: str | None = None,
        solo_activos: bool = True,
        tamanio: int = 50,
        offset: int = 0,
    ) -> list[OrganismoTransito]:
        stmt = select(OrganismoTransitoModelo)
        if solo_activos:
            stmt = stmt.where(OrganismoTransitoModelo.activo.is_(True))
        if departamento:
            stmt = stmt.where(OrganismoTransitoModelo.departamento.ilike(f"%{departamento}%"))
        if q:
            stmt = stmt.where(
                or_(
                    OrganismoTransitoModelo.nombre.ilike(f"%{q}%"),
                    OrganismoTransitoModelo.municipio.ilike(f"%{q}%"),
                    OrganismoTransitoModelo.departamento.ilike(f"%{q}%"),
                )
            )
        stmt = stmt.order_by(OrganismoTransitoModelo.departamento, OrganismoTransitoModelo.nombre)
        stmt = stmt.offset(offset).limit(tamanio)
        filas = (await self._session.execute(stmt)).scalars().all()
        return [self._a_entidad(f) for f in filas]

    def _a_entidad(self, m: OrganismoTransitoModelo) -> OrganismoTransito:
        org = OrganismoTransito(
            nombre=m.nombre,
            codigo=m.public_id,
            municipio=m.municipio,
            departamento=m.departamento,
            id=m.id,
            public_id=m.public_id,
            activo=m.activo,
            creado_en=m.creado_en,
            actualizado_en=m.actualizado_en,
        )
        org.tipo = m.tipo
        org.telefono = m.telefono
        org.direccion = m.direccion
        return org
