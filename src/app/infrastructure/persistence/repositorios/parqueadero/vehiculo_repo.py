import base64
import json
from datetime import datetime, timezone
from uuid import UUID
from typing import Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.entities.parqueadero.vehiculo import VehiculoParqueadero, TipoVehiculoParqueadero
from app.domain.ports.outbound.parqueadero.repositorio_vehiculo import (
    RepositorioVehiculo, FiltrosVehiculo, PaginaVehiculos,
)
from app.infrastructure.persistence.modelos.parqueadero.vehiculo_modelo import VehiculoParqueaderoModelo


def _encode_cursor(creado_en: datetime, id: UUID) -> str:
    return base64.urlsafe_b64encode(json.dumps([creado_en.isoformat(), str(id)]).encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    data = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
    dt = datetime.fromisoformat(data[0])
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt, UUID(data[1])


class VehiculoRepositorioSQL(RepositorioVehiculo):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def guardar(self, v: VehiculoParqueadero) -> VehiculoParqueadero:
        modelo = VehiculoParqueaderoModelo(
            id=v.id,
            public_id=v.public_id,
            placa=v.placa,
            marca=v.marca,
            modelo=v.modelo,
            tipo_vehiculo=v.tipo_vehiculo.value,
            soat_aseguradora=v.soat_aseguradora or None,
            soat_vencimiento=v.soat_vencimiento,
            tecnomecanica_vencimiento=v.tecnomecanica_vencimiento,
            activo=v.activo,
            version=v.version,
            creado_en=v.creado_en,
            actualizado_en=v.actualizado_en,
            organization_id=v.organization_id,
            creado_por=v.creado_por,
        )
        self._session.add(modelo)
        await self._session.flush()
        return self._a_entidad(modelo)

    async def actualizar(self, v: VehiculoParqueadero) -> VehiculoParqueadero:
        modelo = await self._session.get(VehiculoParqueaderoModelo, v.id)
        if not modelo:
            raise ValueError(f"Vehículo {v.id} no encontrado")
        modelo.marca = v.marca
        modelo.modelo = v.modelo
        modelo.tipo_vehiculo = v.tipo_vehiculo.value
        modelo.soat_aseguradora = v.soat_aseguradora or None
        modelo.soat_vencimiento = v.soat_vencimiento
        modelo.tecnomecanica_vencimiento = v.tecnomecanica_vencimiento
        modelo.activo = v.activo
        modelo.actualizado_en = v.actualizado_en
        await self._session.flush()
        return self._a_entidad(modelo)

    async def buscar_por_id(self, id: UUID) -> Optional[VehiculoParqueadero]:
        m = await self._session.get(VehiculoParqueaderoModelo, id)
        return self._a_entidad(m) if m else None

    async def buscar_por_public_id(self, public_id: str) -> Optional[VehiculoParqueadero]:
        result = await self._session.execute(
            select(VehiculoParqueaderoModelo).where(VehiculoParqueaderoModelo.public_id == public_id)
        )
        m = result.scalar_one_or_none()
        return self._a_entidad(m) if m else None

    async def buscar_por_placa(self, placa: str, organization_id: UUID | None = None) -> Optional[VehiculoParqueadero]:
        conds = [VehiculoParqueaderoModelo.placa == placa.upper()]
        if organization_id:
            conds.append(VehiculoParqueaderoModelo.organization_id == organization_id)
        result = await self._session.execute(select(VehiculoParqueaderoModelo).where(and_(*conds)))
        m = result.scalar_one_or_none()
        return self._a_entidad(m) if m else None

    async def listar(self, filtros: FiltrosVehiculo) -> PaginaVehiculos:
        conds = []
        if filtros.organization_id:
            conds.append(VehiculoParqueaderoModelo.organization_id == filtros.organization_id)
        if filtros.placa:
            conds.append(VehiculoParqueaderoModelo.placa.ilike(f"%{filtros.placa}%"))
        if filtros.activo is not None:
            conds.append(VehiculoParqueaderoModelo.activo == filtros.activo)
        if filtros.cursor:
            cursor_dt, cursor_id = _decode_cursor(filtros.cursor)
            conds.append(
                (VehiculoParqueaderoModelo.creado_en < cursor_dt)
                | ((VehiculoParqueaderoModelo.creado_en == cursor_dt) & (VehiculoParqueaderoModelo.id < cursor_id))
            )
        stmt = (
            select(VehiculoParqueaderoModelo)
            .where(and_(*conds) if conds else True)
            .order_by(VehiculoParqueaderoModelo.creado_en.desc(), VehiculoParqueaderoModelo.id.desc())
            .limit(filtros.tamanio + 1)
        )
        filas = (await self._session.execute(stmt)).scalars().all()
        tiene_siguiente = len(filas) > filtros.tamanio
        items = [self._a_entidad(f) for f in filas[:filtros.tamanio]]
        siguiente_cursor = _encode_cursor(items[-1].creado_en, items[-1].id) if tiene_siguiente else None
        return PaginaVehiculos(items=items, siguiente_cursor=siguiente_cursor, tamanio=len(items))

    async def existe_placa(self, placa: str, organization_id: UUID | None = None) -> bool:
        conds = [VehiculoParqueaderoModelo.placa == placa.upper()]
        if organization_id:
            conds.append(VehiculoParqueaderoModelo.organization_id == organization_id)
        result = await self._session.execute(
            select(VehiculoParqueaderoModelo.id).where(and_(*conds)).limit(1)
        )
        return result.scalar_one_or_none() is not None

    def _a_entidad(self, m: VehiculoParqueaderoModelo) -> VehiculoParqueadero:
        return VehiculoParqueadero(
            id=m.id,
            public_id=m.public_id,
            placa=m.placa,
            marca=m.marca or "",
            modelo=m.modelo or "",
            tipo_vehiculo=TipoVehiculoParqueadero(m.tipo_vehiculo),
            soat_aseguradora=m.soat_aseguradora or "",
            soat_vencimiento=m.soat_vencimiento,
            tecnomecanica_vencimiento=m.tecnomecanica_vencimiento,
            activo=m.activo,
            version=m.version,
            creado_en=m.creado_en,
            actualizado_en=m.actualizado_en,
            organization_id=m.organization_id,
            creado_por=m.creado_por,
        )
