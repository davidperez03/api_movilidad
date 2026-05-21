from datetime import datetime
from uuid import UUID
from typing import Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.entities.movilidad.cuenta import CuentaVehiculo, TipoServicio
from app.domain.ports.outbound.movilidad.repositorio_cuenta import (
    RepositorioCuenta, FiltrosCuenta, PaginaCuentas,
)
from app.infrastructure.persistence.modelos.movilidad.cuenta_modelo import CuentaVehiculoModelo
from app.infrastructure.persistence.repositorios._cursor import encode_cursor, decode_cursor


class CuentaRepositorioSQL(RepositorioCuenta):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def guardar(self, cuenta: CuentaVehiculo) -> CuentaVehiculo:
        modelo = CuentaVehiculoModelo(
            id=cuenta.id,
            public_id=cuenta.public_id,
            placa=cuenta.placa,
            numero_cuenta=cuenta.numero_cuenta or "",
            tipo_servicio=cuenta.tipo_servicio.value,
            version=cuenta.version,
            creado_en=cuenta.creado_en,
            actualizado_en=cuenta.actualizado_en,
            organization_id=cuenta.organization_id,
            creado_por=cuenta.creado_por,
        )
        self._session.add(modelo)
        await self._session.flush()
        return self._a_entidad(modelo)

    async def actualizar(self, cuenta: CuentaVehiculo) -> CuentaVehiculo:
        modelo = await self._session.get(CuentaVehiculoModelo, cuenta.id)
        if not modelo:
            raise ValueError(f"Cuenta {cuenta.id} no encontrada")
        modelo.tipo_servicio = cuenta.tipo_servicio.value
        modelo.actualizado_en = cuenta.actualizado_en
        await self._session.flush()
        return self._a_entidad(modelo)

    async def buscar_por_id(self, id: UUID) -> Optional[CuentaVehiculo]:
        modelo = await self._session.get(CuentaVehiculoModelo, id)
        return self._a_entidad(modelo) if modelo else None

    async def buscar_por_public_id(self, public_id: str) -> Optional[CuentaVehiculo]:
        stmt = select(CuentaVehiculoModelo).where(CuentaVehiculoModelo.public_id == public_id)
        result = await self._session.execute(stmt)
        m = result.scalar_one_or_none()
        return self._a_entidad(m) if m else None

    async def buscar_por_placa(self, placa: str, organization_id: UUID | None = None) -> Optional[CuentaVehiculo]:
        conds = [CuentaVehiculoModelo.placa == placa.upper()]
        if organization_id:
            conds.append(CuentaVehiculoModelo.organization_id == organization_id)
        result = await self._session.execute(select(CuentaVehiculoModelo).where(and_(*conds)))
        m = result.scalar_one_or_none()
        return self._a_entidad(m) if m else None

    async def listar(self, filtros: FiltrosCuenta) -> PaginaCuentas:
        conds = []
        if filtros.organization_id:
            conds.append(CuentaVehiculoModelo.organization_id == filtros.organization_id)
        if filtros.placa:
            conds.append(CuentaVehiculoModelo.placa.ilike(f"%{filtros.placa}%"))
        if filtros.cursor:
            cursor_dt, cursor_id = decode_cursor(filtros.cursor)
            conds.append(
                (CuentaVehiculoModelo.creado_en < cursor_dt)
                | ((CuentaVehiculoModelo.creado_en == cursor_dt) & (CuentaVehiculoModelo.id < cursor_id))
            )
        stmt = (
            select(CuentaVehiculoModelo)
            .where(and_(*conds) if conds else True)
            .order_by(CuentaVehiculoModelo.creado_en.desc(), CuentaVehiculoModelo.id.desc())
            .limit(filtros.tamanio + 1)
        )
        filas = (await self._session.execute(stmt)).scalars().all()
        tiene_siguiente = len(filas) > filtros.tamanio
        items = [self._a_entidad(f) for f in filas[:filtros.tamanio]]
        siguiente_cursor = encode_cursor(items[-1].creado_en, items[-1].id) if tiene_siguiente else None
        return PaginaCuentas(items=items, siguiente_cursor=siguiente_cursor, tamanio=len(items))

    async def existe_placa(self, placa: str, organization_id: UUID | None = None) -> bool:
        conds = [CuentaVehiculoModelo.placa == placa.upper()]
        if organization_id:
            conds.append(CuentaVehiculoModelo.organization_id == organization_id)
        result = await self._session.execute(
            select(CuentaVehiculoModelo.id).where(and_(*conds)).limit(1)
        )
        return result.scalar_one_or_none() is not None

    def _a_entidad(self, m: CuentaVehiculoModelo) -> CuentaVehiculo:
        return CuentaVehiculo(
            id=m.id,
            public_id=m.public_id,
            placa=m.placa,
            numero_cuenta=m.numero_cuenta or "",
            tipo_servicio=TipoServicio(m.tipo_servicio),
            version=m.version,
            creado_en=m.creado_en,
            actualizado_en=m.actualizado_en,
            organization_id=m.organization_id,
            creado_por=m.creado_por,
        )
