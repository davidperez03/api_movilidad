import base64
import json
from datetime import datetime, timezone
from uuid import UUID
from typing import Optional
from sqlalchemy import select, and_, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.entities.movilidad.cuenta import CuentaVehiculo, TipoServicio
from app.domain.ports.outbound.movilidad.repositorio_cuenta import (
    RepositorioCuenta, FiltrosCuenta, PaginaCuentas,
)
from app.infrastructure.persistence.modelos.movilidad.cuenta_modelo import CuentaVehiculoModelo


def _encode_cursor(creado_en: datetime, id: UUID) -> str:
    data = json.dumps([creado_en.isoformat(), str(id)])
    return base64.urlsafe_b64encode(data.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    data = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
    dt = datetime.fromisoformat(data[0])
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt, UUID(data[1])


class CuentaRepositorioSQL(RepositorioCuenta):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def guardar(self, cuenta: CuentaVehiculo) -> CuentaVehiculo:
        modelo = CuentaVehiculoModelo(
            id=cuenta.id,
            public_id=cuenta.public_id,
            numero_cuenta=cuenta.numero_cuenta or None,
            placa=cuenta.placa,
            tipo_servicio=cuenta.tipo_servicio.value,
            propietario_nombre=cuenta.propietario_nombre,
            propietario_documento=cuenta.propietario_documento,
            activo=cuenta.activo,
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
        modelo.numero_cuenta = cuenta.numero_cuenta or None
        modelo.propietario_nombre = cuenta.propietario_nombre
        modelo.propietario_documento = cuenta.propietario_documento
        modelo.activo = cuenta.activo
        modelo.actualizado_en = cuenta.actualizado_en
        await self._session.flush()
        return self._a_entidad(modelo)

    async def buscar_por_id(self, id: UUID) -> Optional[CuentaVehiculo]:
        modelo = await self._session.get(CuentaVehiculoModelo, id)
        return self._a_entidad(modelo) if modelo else None

    async def buscar_por_public_id(self, public_id: str) -> Optional[CuentaVehiculo]:
        stmt = select(CuentaVehiculoModelo).where(CuentaVehiculoModelo.public_id == public_id)
        result = await self._session.execute(stmt)
        modelo = result.scalar_one_or_none()
        return self._a_entidad(modelo) if modelo else None

    async def buscar_por_placa(self, placa: str, organization_id: UUID | None = None) -> Optional[CuentaVehiculo]:
        conds = [CuentaVehiculoModelo.placa == placa.upper()]
        if organization_id:
            conds.append(CuentaVehiculoModelo.organization_id == organization_id)
        stmt = select(CuentaVehiculoModelo).where(and_(*conds))
        result = await self._session.execute(stmt)
        modelo = result.scalar_one_or_none()
        return self._a_entidad(modelo) if modelo else None

    async def listar(self, filtros: FiltrosCuenta) -> PaginaCuentas:
        conds = []
        if filtros.organization_id:
            conds.append(CuentaVehiculoModelo.organization_id == filtros.organization_id)
        if filtros.placa:
            conds.append(CuentaVehiculoModelo.placa.ilike(f"%{filtros.placa}%"))
        if filtros.activo is not None:
            conds.append(CuentaVehiculoModelo.activo == filtros.activo)

        if filtros.cursor:
            cursor_dt, cursor_id = _decode_cursor(filtros.cursor)
            conds.append(
                (CuentaVehiculoModelo.creado_en < cursor_dt)
                | (
                    (CuentaVehiculoModelo.creado_en == cursor_dt)
                    & (CuentaVehiculoModelo.id < cursor_id)
                )
            )

        stmt = (
            select(CuentaVehiculoModelo)
            .where(and_(*conds) if conds else True)
            .order_by(CuentaVehiculoModelo.creado_en.desc(), CuentaVehiculoModelo.id.desc())
            .limit(filtros.tamanio + 1)
        )
        result = await self._session.execute(stmt)
        filas = result.scalars().all()

        tiene_siguiente = len(filas) > filtros.tamanio
        items = [self._a_entidad(f) for f in filas[:filtros.tamanio]]
        siguiente_cursor = None
        if tiene_siguiente:
            ultimo = items[-1]
            siguiente_cursor = _encode_cursor(ultimo.creado_en, ultimo.id)

        return PaginaCuentas(items=items, siguiente_cursor=siguiente_cursor, tamanio=len(items))

    async def existe_placa(self, placa: str, organization_id: UUID | None = None) -> bool:
        conds = [CuentaVehiculoModelo.placa == placa.upper()]
        if organization_id:
            conds.append(CuentaVehiculoModelo.organization_id == organization_id)
        stmt = select(CuentaVehiculoModelo.id).where(and_(*conds)).limit(1)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def generar_numero_cuenta(self) -> str:
        result = await self._session.execute(text("SELECT generar_numero_cuenta()"))
        return result.scalar_one()

    def _a_entidad(self, m: CuentaVehiculoModelo) -> CuentaVehiculo:
        return CuentaVehiculo(
            id=m.id,
            public_id=m.public_id,
            numero_cuenta=m.numero_cuenta or "",
            placa=m.placa,
            tipo_servicio=TipoServicio(m.tipo_servicio),
            propietario_nombre=m.propietario_nombre,
            propietario_documento=m.propietario_documento,
            activo=m.activo,
            creado_en=m.creado_en,
            actualizado_en=m.actualizado_en,
            organization_id=m.organization_id,
            creado_por=m.creado_por,
        )
