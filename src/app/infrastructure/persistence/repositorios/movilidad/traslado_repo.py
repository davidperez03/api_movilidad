from datetime import datetime
from uuid import UUID
from typing import Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.entities.movilidad.traslado import Traslado, EstadoTraslado, ESTADOS_TERMINALES_TRASLADO
from app.domain.ports.outbound.movilidad.repositorio_traslado import (
    RepositorioTraslado, FiltrosTraslado, PaginaTraslados,
)
from app.infrastructure.persistence.modelos.movilidad.traslado_modelo import TrasladoModelo
from app.infrastructure.persistence.repositorios._cursor import encode_cursor, decode_cursor

_ESTADOS_ACTIVOS = [e.value for e in EstadoTraslado if e.value not in ESTADOS_TERMINALES_TRASLADO]


class TrasladoRepositorioSQL(RepositorioTraslado):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def guardar(self, traslado: Traslado) -> Traslado:
        modelo = TrasladoModelo(
            id=traslado.id,
            public_id=traslado.public_id,
            cuenta_id=traslado.cuenta_id,
            organismo_destino_id=traslado.organismo_destino_id,
            empresa_transportadora_id=traslado.empresa_transportadora_id,
            estado=traslado.estado.value,
            numero_guia=traslado.numero_guia or None,
            observaciones=traslado.observaciones or None,
            aprobado_en=traslado.aprobado_en,
            vencimiento=traslado.vencimiento,
            completado_en=traslado.completado_en,
            version=traslado.version,
            creado_en=traslado.creado_en,
            actualizado_en=traslado.actualizado_en,
            organization_id=traslado.organization_id,
            creado_por=traslado.creado_por,
            actualizado_por=traslado.actualizado_por,
        )
        self._session.add(modelo)
        await self._session.flush()
        return self._a_entidad(modelo)

    async def actualizar(self, traslado: Traslado) -> Traslado:
        modelo = await self._session.get(TrasladoModelo, traslado.id)
        if not modelo:
            raise ValueError(f"Traslado {traslado.id} no encontrado")
        modelo.estado = traslado.estado.value
        modelo.numero_guia = traslado.numero_guia or None
        modelo.observaciones = traslado.observaciones or None
        modelo.organismo_destino_id = traslado.organismo_destino_id
        modelo.empresa_transportadora_id = traslado.empresa_transportadora_id
        modelo.actualizado_en = traslado.actualizado_en
        modelo.actualizado_por = traslado.actualizado_por
        await self._session.flush()
        return self._a_entidad(modelo)

    async def buscar_por_id(self, id: UUID) -> Optional[Traslado]:
        m = await self._session.get(TrasladoModelo, id)
        return self._a_entidad(m) if m else None

    async def buscar_por_public_id(self, public_id: str) -> Optional[Traslado]:
        result = await self._session.execute(
            select(TrasladoModelo).where(TrasladoModelo.public_id == public_id)
        )
        m = result.scalar_one_or_none()
        return self._a_entidad(m) if m else None

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
            conds.append(TrasladoModelo.vencimiento < func.current_date())
            conds.append(TrasladoModelo.estado.in_(_ESTADOS_ACTIVOS))
        if filtros.cursor:
            cursor_dt, cursor_id = decode_cursor(filtros.cursor)
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
        filas = (await self._session.execute(stmt)).scalars().all()
        tiene_siguiente = len(filas) > filtros.tamanio
        items = [self._a_entidad(f) for f in filas[:filtros.tamanio]]
        siguiente_cursor = encode_cursor(items[-1].creado_en, items[-1].id) if tiene_siguiente else None
        return PaginaTraslados(items=items, siguiente_cursor=siguiente_cursor, tamanio=len(items))

    async def tiene_proceso_activo(self, cuenta_id: UUID) -> bool:
        result = await self._session.execute(
            select(TrasladoModelo.id)
            .where(TrasladoModelo.cuenta_id == cuenta_id, TrasladoModelo.estado.in_(_ESTADOS_ACTIVOS))
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def ultimo_completado(self, cuenta_id: UUID) -> Optional[Traslado]:
        result = await self._session.execute(
            select(TrasladoModelo)
            .where(
                TrasladoModelo.cuenta_id == cuenta_id,
                TrasladoModelo.estado == EstadoTraslado.TRASLADADO.value,
            )
            .order_by(TrasladoModelo.actualizado_en.desc())
            .limit(1)
        )
        m = result.scalar_one_or_none()
        return self._a_entidad(m) if m else None

    def _a_entidad(self, m: TrasladoModelo) -> Traslado:
        return Traslado(
            id=m.id,
            public_id=m.public_id,
            cuenta_id=m.cuenta_id,
            organismo_destino_id=m.organismo_destino_id,
            empresa_transportadora_id=m.empresa_transportadora_id,
            estado=EstadoTraslado(m.estado),
            numero_guia=m.numero_guia or "",
            observaciones=m.observaciones or "",
            aprobado_en=m.aprobado_en,
            vencimiento=m.vencimiento,
            completado_en=m.completado_en,
            version=m.version,
            creado_en=m.creado_en,
            actualizado_en=m.actualizado_en,
            organization_id=m.organization_id,
            creado_por=m.creado_por,
            actualizado_por=m.actualizado_por,
        )
