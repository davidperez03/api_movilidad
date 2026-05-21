from datetime import datetime
from uuid import UUID
from typing import Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.entities.movilidad.novedad import Novedad, TipoNovedad, PrioridadNovedad, EstadoNovedad
from app.domain.ports.outbound.movilidad.repositorio_novedad import (
    RepositorioNovedad, FiltrosNovedad, PaginaNovedades,
)
from app.infrastructure.persistence.modelos.movilidad.novedad_modelo import NovedadModelo
from app.infrastructure.persistence.repositorios._cursor import encode_cursor, decode_cursor


class NovedadRepositorioSQL(RepositorioNovedad):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def guardar(self, novedad: Novedad) -> Novedad:
        modelo = NovedadModelo(
            id=novedad.id,
            public_id=novedad.public_id,
            proceso_tipo=novedad.proceso_tipo,
            proceso_id=novedad.proceso_id,
            tipo_novedad=novedad.tipo_novedad.value,
            prioridad=novedad.prioridad.value,
            descripcion=novedad.descripcion,
            estado=novedad.estado.value,
            solucion=novedad.solucion or None,
            resuelto_por=novedad.resuelto_por,
            resuelto_en=novedad.resuelto_en,
            creado_en=novedad.creado_en,
            actualizado_en=novedad.actualizado_en,
            organization_id=novedad.organization_id,
            creado_por=novedad.creado_por,
        )
        self._session.add(modelo)
        await self._session.flush()
        return self._a_entidad(modelo)

    async def actualizar(self, novedad: Novedad) -> Novedad:
        modelo = await self._session.get(NovedadModelo, novedad.id)
        if not modelo:
            raise ValueError(f"Novedad {novedad.id} no encontrada")
        modelo.estado = novedad.estado.value
        modelo.solucion = novedad.solucion or None
        modelo.resuelto_por = novedad.resuelto_por
        modelo.resuelto_en = novedad.resuelto_en
        modelo.actualizado_en = novedad.actualizado_en
        await self._session.flush()
        return self._a_entidad(modelo)

    async def buscar_por_id(self, id: UUID) -> Optional[Novedad]:
        m = await self._session.get(NovedadModelo, id)
        return self._a_entidad(m) if m else None

    async def buscar_por_public_id(self, public_id: str) -> Optional[Novedad]:
        result = await self._session.execute(
            select(NovedadModelo).where(NovedadModelo.public_id == public_id)
        )
        m = result.scalar_one_or_none()
        return self._a_entidad(m) if m else None

    async def listar(self, filtros: FiltrosNovedad) -> PaginaNovedades:
        conds = []
        if filtros.organization_id:
            conds.append(NovedadModelo.organization_id == filtros.organization_id)
        if filtros.traslado_id:
            conds.append(NovedadModelo.proceso_tipo == "traslado")
            conds.append(NovedadModelo.proceso_id == filtros.traslado_id)
        if filtros.radicacion_id:
            conds.append(NovedadModelo.proceso_tipo == "radicacion")
            conds.append(NovedadModelo.proceso_id == filtros.radicacion_id)
        if filtros.estado:
            conds.append(NovedadModelo.estado == filtros.estado.value)
        if filtros.cursor:
            cursor_dt, cursor_id = decode_cursor(filtros.cursor)
            conds.append(
                (NovedadModelo.creado_en < cursor_dt)
                | ((NovedadModelo.creado_en == cursor_dt) & (NovedadModelo.id < cursor_id))
            )
        stmt = (
            select(NovedadModelo)
            .where(and_(*conds) if conds else True)
            .order_by(NovedadModelo.creado_en.desc(), NovedadModelo.id.desc())
            .limit(filtros.tamanio + 1)
        )
        filas = (await self._session.execute(stmt)).scalars().all()
        tiene_siguiente = len(filas) > filtros.tamanio
        items = [self._a_entidad(f) for f in filas[:filtros.tamanio]]
        siguiente_cursor = encode_cursor(items[-1].creado_en, items[-1].id) if tiene_siguiente else None
        return PaginaNovedades(items=items, siguiente_cursor=siguiente_cursor, tamanio=len(items))

    async def novedades_pendientes_cuenta(self, proceso_id: UUID) -> list[Novedad]:
        result = await self._session.execute(
            select(NovedadModelo).where(
                NovedadModelo.proceso_id == proceso_id,
                NovedadModelo.estado != EstadoNovedad.RESUELTA.value,
            )
        )
        return [self._a_entidad(m) for m in result.scalars().all()]

    def _a_entidad(self, m: NovedadModelo) -> Novedad:
        return Novedad(
            id=m.id,
            public_id=m.public_id,
            proceso_tipo=m.proceso_tipo,
            proceso_id=m.proceso_id,
            tipo_novedad=TipoNovedad(m.tipo_novedad),
            prioridad=PrioridadNovedad(m.prioridad),
            descripcion=m.descripcion,
            estado=EstadoNovedad(m.estado),
            solucion=m.solucion or "",
            resuelto_por=m.resuelto_por,
            resuelto_en=m.resuelto_en,
            creado_en=m.creado_en,
            actualizado_en=m.actualizado_en,
            organization_id=m.organization_id,
            creado_por=m.creado_por,
        )
