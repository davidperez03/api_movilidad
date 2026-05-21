import base64
import json
from datetime import datetime, timezone
from uuid import UUID
from typing import Optional
from sqlalchemy import select, and_, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.entities.nunc.sesion import SesionNunc, EstadoSesionNunc
from app.domain.entities.nunc.registro import RegistroNunc
from app.domain.ports.outbound.nunc.repositorio_sesion import (
    RepositorioSesionNunc, FiltrosRegistroNunc, PaginaRegistrosNunc,
)
from app.infrastructure.persistence.modelos.nunc.sesion_modelo import SesionNuncModelo, RegistroNuncModelo


def _encode_cursor(creado_en: datetime, id: UUID) -> str:
    data = json.dumps([creado_en.isoformat(), str(id)])
    return base64.urlsafe_b64encode(data.encode()).decode()


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
        codigo = await self._session.execute(text("SELECT generar_codigo_nunc()"))
        sesion.codigo = codigo.scalar_one()

        modelo = SesionNuncModelo(
            id=sesion.id,
            public_id=sesion.public_id,
            codigo=sesion.codigo,
            estado=sesion.estado.value,
            expira_en=sesion.expira_en,
            cerrado_en=sesion.cerrado_en,
            creado_en=sesion.creado_en,
            actualizado_en=sesion.actualizado_en,
            organization_id=sesion.organization_id,
            creado_por=sesion.creado_por,
        )
        self._session.add(modelo)
        await self._session.flush()
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
        stmt = select(SesionNuncModelo).where(SesionNuncModelo.codigo == codigo.upper())
        result = await self._session.execute(stmt)
        modelo = result.scalar_one_or_none()
        return self._a_sesion(modelo) if modelo else None

    async def buscar_sesion_por_public_id(self, public_id: str) -> Optional[SesionNunc]:
        stmt = select(SesionNuncModelo).where(SesionNuncModelo.public_id == public_id)
        result = await self._session.execute(stmt)
        modelo = result.scalar_one_or_none()
        return self._a_sesion(modelo) if modelo else None

    async def guardar_registro(self, registro: RegistroNunc) -> RegistroNunc:
        modelo = RegistroNuncModelo(
            id=registro.id,
            public_id=registro.public_id,
            sesion_id=registro.sesion_id,
            placa=registro.placa,
            nombre_conductor=registro.nombre_conductor,
            documento_conductor=registro.documento_conductor,
            datos_forenses=registro.datos_forenses,
            creado_en=registro.creado_en,
            organization_id=registro.organization_id,
            creado_por=registro.creado_por,
        )
        self._session.add(modelo)
        await self._session.flush()
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
        result = await self._session.execute(stmt)
        filas = result.scalars().all()

        tiene_siguiente = len(filas) > filtros.tamanio
        items = [self._a_registro(f) for f in filas[:filtros.tamanio]]
        siguiente_cursor = None
        if tiene_siguiente:
            ultimo = items[-1]
            siguiente_cursor = _encode_cursor(ultimo.creado_en, ultimo.id)

        return PaginaRegistrosNunc(items=items, siguiente_cursor=siguiente_cursor, tamanio=len(items))

    def _a_sesion(self, m: SesionNuncModelo) -> SesionNunc:
        s = SesionNunc.__new__(SesionNunc)
        s.id = m.id
        s.public_id = m.public_id
        s.codigo = m.codigo
        s.estado = EstadoSesionNunc(m.estado)
        s.expira_en = m.expira_en
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
            nombre_conductor=m.nombre_conductor,
            documento_conductor=m.documento_conductor,
            numero_secuencial=m.numero_secuencial,
            datos_forenses=m.datos_forenses or {},
            creado_en=m.creado_en,
            organization_id=m.organization_id,
            creado_por=m.creado_por,
        )
