from datetime import datetime
from uuid import UUID
from typing import Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.entities.parqueadero.inspeccion import Inspeccion, TurnoInspeccion, EstadoItem
from app.domain.ports.outbound.parqueadero.repositorio_inspeccion import (
    RepositorioInspeccion, FiltrosInspeccion, PaginaInspecciones,
)
from app.infrastructure.persistence.repositorios._cursor import encode_cursor, decode_cursor
from app.infrastructure.persistence.modelos.parqueadero.inspeccion_modelo import InspeccionModelo




class InspeccionRepositorioSQL(RepositorioInspeccion):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def guardar(self, ins: Inspeccion) -> Inspeccion:
        modelo = InspeccionModelo(
            id=ins.id,
            public_id=ins.public_id,
            codigo=ins.codigo,
            vehiculo_id=ins.vehiculo_id,
            operador_id=ins.operador_id,
            auxiliar_id=ins.auxiliar_id,
            inspector_id=ins.inspector_id,
            fecha=ins.fecha,
            hora=ins.hora,
            turno=ins.turno.value,
            es_apto=ins.es_apto,
            observaciones=ins.observaciones or None,
            firma_operador=ins.firma_operador or None,
            firma_inspector=ins.firma_inspector or None,
            fotos=ins.fotos,
            soat_vencimiento_snap=ins.soat_vencimiento_snap,
            tecnomecanica_vencimiento_snap=ins.tecnomecanica_vencimiento_snap,
            licencia_vencimiento_snap=ins.licencia_vencimiento_snap,
            version=ins.version,
            creado_en=ins.creado_en,
            actualizado_en=ins.actualizado_en,
            organization_id=ins.organization_id,
            creado_por=ins.creado_por,
            actualizado_por=ins.actualizado_por,
        )
        self._session.add(modelo)
        await self._session.flush()
        return self._a_entidad(modelo)

    async def actualizar(self, ins: Inspeccion) -> Inspeccion:
        modelo = await self._session.get(InspeccionModelo, ins.id)
        if not modelo:
            raise ValueError(f"Inspección {ins.id} no encontrada")
        modelo.es_apto = ins.es_apto
        modelo.observaciones = ins.observaciones or None
        modelo.firma_operador = ins.firma_operador or None
        modelo.firma_inspector = ins.firma_inspector or None
        modelo.fotos = ins.fotos
        modelo.actualizado_en = ins.actualizado_en
        modelo.actualizado_por = ins.actualizado_por
        await self._session.flush()
        return self._a_entidad(modelo)

    async def buscar_por_id(self, id: UUID) -> Optional[Inspeccion]:
        m = await self._session.get(InspeccionModelo, id)
        return self._a_entidad(m) if m else None

    async def buscar_por_public_id(self, public_id: str) -> Optional[Inspeccion]:
        result = await self._session.execute(
            select(InspeccionModelo).where(InspeccionModelo.public_id == public_id)
        )
        m = result.scalar_one_or_none()
        return self._a_entidad(m) if m else None

    async def listar(self, filtros: FiltrosInspeccion) -> PaginaInspecciones:
        conds = []
        if filtros.organization_id:
            conds.append(InspeccionModelo.organization_id == filtros.organization_id)
        if filtros.vehiculo_id:
            conds.append(InspeccionModelo.vehiculo_id == filtros.vehiculo_id)
        if filtros.personal_id:
            conds.append(InspeccionModelo.operador_id == filtros.personal_id)
        if filtros.es_apto is not None:
            conds.append(InspeccionModelo.es_apto == filtros.es_apto)
        if filtros.cursor:
            cursor_dt, cursor_id = decode_cursor(filtros.cursor)
            conds.append(
                (InspeccionModelo.creado_en < cursor_dt)
                | ((InspeccionModelo.creado_en == cursor_dt) & (InspeccionModelo.id < cursor_id))
            )
        stmt = (
            select(InspeccionModelo)
            .where(and_(*conds) if conds else True)
            .order_by(InspeccionModelo.creado_en.desc(), InspeccionModelo.id.desc())
            .limit(filtros.tamanio + 1)
        )
        filas = (await self._session.execute(stmt)).scalars().all()
        tiene_siguiente = len(filas) > filtros.tamanio
        items = [self._a_entidad(f) for f in filas[:filtros.tamanio]]
        siguiente_cursor = encode_cursor(items[-1].creado_en, items[-1].id) if tiene_siguiente else None
        return PaginaInspecciones(items=items, siguiente_cursor=siguiente_cursor, tamanio=len(items))

    def _a_entidad(self, m: InspeccionModelo) -> Inspeccion:
        return Inspeccion(
            id=m.id,
            public_id=m.public_id,
            codigo=m.codigo,
            vehiculo_id=m.vehiculo_id,
            operador_id=m.operador_id,
            auxiliar_id=m.auxiliar_id,
            inspector_id=m.inspector_id,
            fecha=m.fecha,
            hora=m.hora,
            turno=TurnoInspeccion(m.turno),
            es_apto=m.es_apto,
            observaciones=m.observaciones or "",
            firma_operador=m.firma_operador or "",
            firma_inspector=m.firma_inspector or "",
            fotos=m.fotos or [],
            soat_vencimiento_snap=m.soat_vencimiento_snap,
            tecnomecanica_vencimiento_snap=m.tecnomecanica_vencimiento_snap,
            licencia_vencimiento_snap=m.licencia_vencimiento_snap,
            version=m.version,
            creado_en=m.creado_en,
            actualizado_en=m.actualizado_en,
            organization_id=m.organization_id,
            creado_por=m.creado_por,
            actualizado_por=m.actualizado_por,
        )
