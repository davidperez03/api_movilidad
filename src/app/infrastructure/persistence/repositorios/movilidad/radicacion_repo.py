import base64
import json
from datetime import datetime, timezone
from uuid import UUID
from typing import Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.entities.movilidad.radicacion import Radicacion, EstadoRadicacion
from app.domain.ports.outbound.movilidad.repositorio_radicacion import (
    RepositorioRadicacion, FiltrosRadicacion, PaginaRadicaciones,
)
from app.infrastructure.persistence.modelos.movilidad.radicacion_modelo import RadicacionModelo

_ESTADOS_ACTIVOS = [e.value for e in EstadoRadicacion if e != EstadoRadicacion.RADICADO]


def _encode_cursor(creado_en: datetime, id: UUID) -> str:
    return base64.urlsafe_b64encode(json.dumps([creado_en.isoformat(), str(id)]).encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    data = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
    dt = datetime.fromisoformat(data[0])
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt, UUID(data[1])


class RadicacionRepositorioSQL(RepositorioRadicacion):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def guardar(self, radicacion: Radicacion) -> Radicacion:
        modelo = RadicacionModelo(
            id=radicacion.id,
            public_id=radicacion.public_id,
            cuenta_id=radicacion.cuenta_id,
            organismo_origen_id=radicacion.organismo_origen_id,
            empresa_transportadora_id=radicacion.empresa_transportadora_id,
            estado=radicacion.estado.value,
            numero_guia=radicacion.numero_guia or None,
            numero_guia_devolucion=radicacion.numero_guia_devolucion or None,
            observaciones=radicacion.observaciones or None,
            radicado_en=radicacion.radicado_en,
            vencimiento=radicacion.vencimiento,
            completado_en=radicacion.completado_en,
            version=radicacion.version,
            creado_en=radicacion.creado_en,
            actualizado_en=radicacion.actualizado_en,
            organization_id=radicacion.organization_id,
            creado_por=radicacion.creado_por,
            actualizado_por=radicacion.actualizado_por,
        )
        self._session.add(modelo)
        await self._session.flush()
        return self._a_entidad(modelo)

    async def actualizar(self, radicacion: Radicacion) -> Radicacion:
        modelo = await self._session.get(RadicacionModelo, radicacion.id)
        if not modelo:
            raise ValueError(f"Radicacion {radicacion.id} no encontrada")
        modelo.estado = radicacion.estado.value
        modelo.numero_guia = radicacion.numero_guia or None
        modelo.numero_guia_devolucion = radicacion.numero_guia_devolucion or None
        modelo.observaciones = radicacion.observaciones or None
        modelo.organismo_origen_id = radicacion.organismo_origen_id
        modelo.empresa_transportadora_id = radicacion.empresa_transportadora_id
        modelo.radicado_en = radicacion.radicado_en
        modelo.actualizado_en = radicacion.actualizado_en
        modelo.actualizado_por = radicacion.actualizado_por
        await self._session.flush()
        return self._a_entidad(modelo)

    async def buscar_por_id(self, id: UUID) -> Optional[Radicacion]:
        m = await self._session.get(RadicacionModelo, id)
        return self._a_entidad(m) if m else None

    async def buscar_por_public_id(self, public_id: str) -> Optional[Radicacion]:
        result = await self._session.execute(
            select(RadicacionModelo).where(RadicacionModelo.public_id == public_id)
        )
        m = result.scalar_one_or_none()
        return self._a_entidad(m) if m else None

    async def listar(self, filtros: FiltrosRadicacion) -> PaginaRadicaciones:
        conds = []
        if filtros.organization_id:
            conds.append(RadicacionModelo.organization_id == filtros.organization_id)
        if filtros.cuenta_id:
            conds.append(RadicacionModelo.cuenta_id == filtros.cuenta_id)
        if filtros.estado:
            conds.append(RadicacionModelo.estado == filtros.estado.value)
        if filtros.vencidos is True:
            from sqlalchemy import func
            conds.append(RadicacionModelo.vencimiento < func.current_date())
            conds.append(RadicacionModelo.estado.in_(_ESTADOS_ACTIVOS))
        if filtros.cursor:
            cursor_dt, cursor_id = _decode_cursor(filtros.cursor)
            conds.append(
                (RadicacionModelo.creado_en < cursor_dt)
                | ((RadicacionModelo.creado_en == cursor_dt) & (RadicacionModelo.id < cursor_id))
            )
        stmt = (
            select(RadicacionModelo)
            .where(and_(*conds) if conds else True)
            .order_by(RadicacionModelo.creado_en.desc(), RadicacionModelo.id.desc())
            .limit(filtros.tamanio + 1)
        )
        filas = (await self._session.execute(stmt)).scalars().all()
        tiene_siguiente = len(filas) > filtros.tamanio
        items = [self._a_entidad(f) for f in filas[:filtros.tamanio]]
        siguiente_cursor = _encode_cursor(items[-1].creado_en, items[-1].id) if tiene_siguiente else None
        return PaginaRadicaciones(items=items, siguiente_cursor=siguiente_cursor, tamanio=len(items))

    async def tiene_proceso_activo(self, cuenta_id: UUID) -> bool:
        result = await self._session.execute(
            select(RadicacionModelo.id)
            .where(RadicacionModelo.cuenta_id == cuenta_id, RadicacionModelo.estado.in_(_ESTADOS_ACTIVOS))
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    def _a_entidad(self, m: RadicacionModelo) -> Radicacion:
        return Radicacion(
            id=m.id,
            public_id=m.public_id,
            cuenta_id=m.cuenta_id,
            organismo_origen_id=m.organismo_origen_id,
            empresa_transportadora_id=m.empresa_transportadora_id,
            estado=EstadoRadicacion(m.estado),
            numero_guia=m.numero_guia or "",
            numero_guia_devolucion=m.numero_guia_devolucion or "",
            observaciones=m.observaciones or "",
            radicado_en=m.radicado_en,
            vencimiento=m.vencimiento,
            completado_en=m.completado_en,
            version=m.version,
            creado_en=m.creado_en,
            actualizado_en=m.actualizado_en,
            organization_id=m.organization_id,
            creado_por=m.creado_por,
            actualizado_por=m.actualizado_por,
        )
