from uuid import UUID
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.entities.movilidad.empresa import EmpresaTransporte
from app.infrastructure.persistence.modelos.movilidad.empresa_modelo import EmpresaTransporteModelo


class EmpresaRepositorioSQL:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def guardar(self, emp: EmpresaTransporte) -> EmpresaTransporte:
        modelo = EmpresaTransporteModelo(
            id=emp.id,
            public_id=emp.public_id,
            nombre=emp.nombre,
            activo=emp.activo,
            creado_en=emp.creado_en,
            actualizado_en=emp.actualizado_en,
        )
        self._session.add(modelo)
        await self._session.flush()
        return self._a_entidad(modelo)

    async def buscar_por_id(self, id: UUID) -> Optional[EmpresaTransporte]:
        m = await self._session.get(EmpresaTransporteModelo, id)
        return self._a_entidad(m) if m else None

    async def buscar_por_public_id(self, public_id: str) -> Optional[EmpresaTransporte]:
        result = await self._session.execute(
            select(EmpresaTransporteModelo).where(EmpresaTransporteModelo.public_id == public_id)
        )
        m = result.scalar_one_or_none()
        return self._a_entidad(m) if m else None

    async def listar(
        self,
        q: str | None = None,
        solo_activos: bool = True,
        tamanio: int = 50,
        offset: int = 0,
    ) -> list[EmpresaTransporte]:
        stmt = select(EmpresaTransporteModelo)
        if solo_activos:
            stmt = stmt.where(EmpresaTransporteModelo.activo.is_(True))
        if q:
            stmt = stmt.where(EmpresaTransporteModelo.nombre.ilike(f"%{q}%"))
        stmt = stmt.order_by(EmpresaTransporteModelo.nombre).offset(offset).limit(tamanio)
        filas = (await self._session.execute(stmt)).scalars().all()
        return [self._a_entidad(f) for f in filas]

    def _a_entidad(self, m: EmpresaTransporteModelo) -> EmpresaTransporte:
        return EmpresaTransporte(
            nombre=m.nombre,
            nit="",
            id=m.id,
            public_id=m.public_id,
            activo=m.activo,
            creado_en=m.creado_en,
            actualizado_en=m.actualizado_en,
        )
