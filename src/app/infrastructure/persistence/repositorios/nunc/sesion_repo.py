import base64
import json
from datetime import datetime, timezone
from uuid import UUID
from typing import Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.entities.nunc.sesion import SesionNunc, EstadoSesionNunc
from app.domain.entities.nunc.registro import RegistroNunc
from app.domain.ports.outbound.nunc.repositorio_sesion import (
    RepositorioSesionNunc, FiltrosRegistroNunc, PaginaRegistrosNunc,
)
from app.infrastructure.persistence.modelos.nunc.sesion_modelo import SesionNuncModelo, RegistroNuncModelo


def _encode_cursor(creado_en: datetime, id: UUID) -> str:
    return base64.urlsafe_b64encode(json.dumps([creado_en.isoformat(), str(id)]).encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    data = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
    dt = datetime.fromisoformat(data[0])
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt, UUID(data[1])


class SesionNuncRepositorioSQL(RepositorioSesionNunc):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def guardar_sesion(self, sesion: SesionNunc) -> SesionNunc:
        # codigo_sesion lo genera el trigger BD al INSERT
        modelo = SesionNuncModelo(
            id=sesion.id,
            public_id=sesion.public_id,
            codigo_sesion="",               # trigger asigna PER-XXXXXX
            nombre_entidad=sesion.nombre_entidad,
            nombre_perito=sesion.nombre_perito,
            departamento=sesion.departamento,
            municipio=sesion.municipio,
            entidad=sesion.entidad,
            unidad=sesion.unidad,
            ano=sesion.ano,
            estado=sesion.estado.value,
            expiracion=sesion.expiracion,
            cerrado_en=sesion.cerrado_en,
            creado_en=sesion.creado_en,
            actualizado_en=sesion.actualizado_en,
            organization_id=sesion.organization_id,
            creado_por=sesion.creado_por,
        )
        self._session.add(modelo)
        await self._session.flush()
        await self._session.refresh(modelo)     # obtener codigo_sesion asignado por trigger
        return self._a_sesion(modelo)

    async def actualizar_sesion(self, sesion: SesionNunc) -> SesionNunc:
        modelo = await self._session.get(SesionNuncModelo, sesion.id)
        if not modelo:
            raise ValueError(f"Sesión {sesion.id} no encontrada")
        modelo.estado = sesion.estado.value
        modelo.cerrado_en = sesion.cerrado_en
        modelo.actualizado_en = sesion.actualizado_en
        await self._session.flush()
        return self._a_sesion(modelo)

    async def buscar_sesion_por_codigo(self, codigo: str) -> Optional[SesionNunc]:
        result = await self._session.execute(
            select(SesionNuncModelo).where(SesionNuncModelo.codigo_sesion == codigo.upper())
        )
        m = result.scalar_one_or_none()
        return self._a_sesion(m) if m else None

    async def buscar_sesion_por_public_id(self, public_id: str) -> Optional[SesionNunc]:
        result = await self._session.execute(
            select(SesionNuncModelo).where(SesionNuncModelo.public_id == public_id)
        )
        m = result.scalar_one_or_none()
        return self._a_sesion(m) if m else None

    async def guardar_registro(self, registro: RegistroNunc) -> RegistroNunc:
        # numero_secuencial lo asigna el trigger BD
        modelo = RegistroNuncModelo(
            id=registro.id,
            public_id=registro.public_id,
            sesion_id=registro.sesion_id,
            placa=registro.placa,
            departamento=registro.departamento,
            municipio=registro.municipio,
            entidad=registro.entidad,
            unidad=registro.unidad,
            ano=registro.ano,
            creado_en=registro.creado_en,
            organization_id=registro.organization_id,
        )
        self._session.add(modelo)
        await self._session.flush()
        await self._session.refresh(modelo)     # obtener numero_secuencial del trigger
        return self._a_registro(modelo)

    async def listar_registros(self, filtros: FiltrosRegistroNunc) -> PaginaRegistrosNunc:
        conds = []
        if filtros.organization_id:
            conds.append(RegistroNuncModelo.organization_id == filtros.organization_id)
        if filtros.sesion_id:
            conds.append(RegistroNuncModelo.sesion_id == filtros.sesion_id)
        if filtros.placa:
            conds.append(RegistroNuncModelo.placa == filtros.placa.upper())
        if filtros.cursor:
            cursor_dt, cursor_id = _decode_cursor(filtros.cursor)
            conds.append(
                (RegistroNuncModelo.creado_en < cursor_dt)
                | ((RegistroNuncModelo.creado_en == cursor_dt) & (RegistroNuncModelo.id < cursor_id))
            )
        stmt = (
            select(RegistroNuncModelo)
            .where(and_(*conds) if conds else True)
            .order_by(RegistroNuncModelo.creado_en.desc(), RegistroNuncModelo.id.desc())
            .limit(filtros.tamanio + 1)
        )
        filas = (await self._session.execute(stmt)).scalars().all()
        tiene_siguiente = len(filas) > filtros.tamanio
        items = [self._a_registro(f) for f in filas[:filtros.tamanio]]
        siguiente_cursor = _encode_cursor(items[-1].creado_en, items[-1].id) if tiene_siguiente else None
        return PaginaRegistrosNunc(items=items, siguiente_cursor=siguiente_cursor, tamanio=len(items))

    def _a_sesion(self, m: SesionNuncModelo) -> SesionNunc:
        s = SesionNunc.__new__(SesionNunc)
        s.id = m.id
        s.public_id = m.public_id
        s.codigo_sesion = m.codigo_sesion
        s.nombre_entidad = m.nombre_entidad
        s.nombre_perito = m.nombre_perito
        s.departamento = m.departamento
        s.municipio = m.municipio
        s.entidad = m.entidad
        s.unidad = m.unidad
        s.ano = m.ano
        s.estado = EstadoSesionNunc(m.estado)
        s.expiracion = m.expiracion
        s.cerrado_en = m.cerrado_en
        s.creado_en = m.creado_en
        s.actualizado_en = m.actualizado_en
        s.organization_id = m.organization_id
        s.creado_por = m.creado_por
        return s

    def _a_registro(self, m: RegistroNuncModelo) -> RegistroNunc:
        return RegistroNunc(
            id=m.id,
            public_id=m.public_id,
            sesion_id=m.sesion_id,
            placa=m.placa,
            departamento=m.departamento,
            municipio=m.municipio,
            entidad=m.entidad,
            unidad=m.unidad,
            ano=m.ano,
            numero_secuencial=m.numero_secuencial,
            creado_en=m.creado_en,
            organization_id=m.organization_id,
        )
