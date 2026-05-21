import base64
import json
from datetime import datetime, timezone
from uuid import UUID
from typing import Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.entities.movilidad.traslado import Traslado, EstadoTraslado
from app.domain.ports.outbound.movilidad.repositorio_traslado import (
    RepositorioTraslado, FiltrosTraslado, PaginaTraslados,
)
from app.infrastructure.persistence.modelos.movilidad.traslado_modelo import TrasladoModelo


def _encode_cursor(creado_en: datetime, id: UUID) -> str:
    data = json.dumps([creado_en.isoformat(), str(id)])
    return base64.urlsafe_b64encode(data.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    data = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
    dt = datetime.fromisoformat(data[0])
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt, UUID(data[1])


_ESTADOS_ACTIVOS = [
    EstadoTraslado.SIN_ASIGNAR.value,
    EstadoTraslado.REVISADO.value,
    EstadoTraslado.CON_NOVEDADES.value,
    EstadoTraslado.APROBADO.value,
    EstadoTraslado.ENVIADO_ORGANISMO.value,
]


class TrasladoRepositorioSQL(RepositorioTraslado):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def guardar(self, traslado: Traslado) -> Traslado:
        modelo = TrasladoModelo(
            id=traslado.id,
            public_id=traslado.public_id,
            cuenta_id=traslado.cuenta_id,
            organismo_destino_id=traslado.organismo_destino_id,
            estado=traslado.estado.value,
            observaciones=traslado.observaciones or None,
            vence_en=traslado.vence_en,
            completado_en=traslado.completado_en,
            creado_en=traslado.creado_en,
            actualizado_en=traslado.actualizado_en,
            organization_id=traslado.organization_id,
            creado_por=traslado.creado_por,
            asignado_a=traslado.asignado_a,
        )
        self._session.add(modelo)
        await self._session.flush()
        return self._a_entidad(modelo)

    async def actualizar(self, traslado: Traslado) -> Traslado:
        modelo = await self._session.get(TrasladoModelo, traslado.id)
        if not modelo:
            raise ValueError(f"Traslado {traslado.id} no encontrado")
        modelo.estado = traslado.estado.value
        modelo.observaciones = traslado.observaciones or None
        modelo.vence_en = traslado.vence_en
        modelo.completado_en = traslado.completado_en
        modelo.actualizado_en = traslado.actualizado_en
        modelo.asignado_a = traslado.asignado_a
        await self._session.flush()
        return self._a_entidad(modelo)

    async def buscar_por_id(self, id: UUID) -> Optional[Traslado]:
        modelo = await self._session.get(TrasladoModelo, id)
        return self._a_entidad(modelo) if modelo else None

    async def buscar_por_public_id(self, public_id: str) -> Optional[Traslado]:
        stmt = select(TrasladoModelo).where(TrasladoModelo.public_id == public_id)
        result = await self._session.execute(stmt)
        modelo = result.scalar_one_or_none()
        return self._a_entidad(modelo) if modelo else None

    async def listar(self, filtros: FiltrosTraslado) -> PaginaTraslados:
        conds = []
        if filtros.organization_id:
            conds.append(TrasladoModelo.organization_id == filtros.organization_id)
        if filtros.cuenta_id:
            conds.append(TrasladoModelo.cuenta_id == filtros.cuenta_id)
        if filtros.estado:
            conds.append(TrasladoModelo.estado == filtros.estado.value)
        if filtros.vencidos is True:
            from sqlalchemy import func
            conds.append(TrasladoModelo.vence_en < func.now())
            conds.append(TrasladoModelo.estado.in_(_ESTADOS_ACTIVOS))

        if filtros.cursor:
            cursor_dt, cursor_id = _decode_cursor(filtros.cursor)
            conds.append(
                (TrasladoModelo.creado_en < cursor_dt)
                | ((TrasladoModelo.creado_en == cursor_dt) & (TrasladoModelo.id < cursor_id))
            )

        stmt = (
            select(TrasladoModelo)
            .where(and_(*conds) if conds else True)
            .order_by(TrasladoModelo.creado_en.desc(), TrasladoModelo.id.desc())
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

        return PaginaTraslados(items=items, siguiente_cursor=siguiente_cursor, tamanio=len(items))

    async def tiene_proceso_activo(self, cuenta_id: UUID) -> bool:
        stmt = (
            select(TrasladoModelo.id)
            .where(
                TrasladoModelo.cuenta_id == cuenta_id,
                TrasladoModelo.estado.in_(_ESTADOS_ACTIVOS),
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    def _a_entidad(self, m: TrasladoModelo) -> Traslado:
        return Traslado(
            id=m.id,
            public_id=m.public_id,
            cuenta_id=m.cuenta_id,
            organismo_destino_id=m.organismo_destino_id,
            estado=EstadoTraslado(m.estado),
            observaciones=m.observaciones or "",
            vence_en=m.vence_en,
            completado_en=m.completado_en,
            creado_en=m.creado_en,
            actualizado_en=m.actualizado_en,
            organization_id=m.organization_id,
            creado_por=m.creado_por,
            asignado_a=m.asignado_a,
        )
