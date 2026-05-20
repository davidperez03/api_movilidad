import base64
import json
from datetime import datetime, timezone
from uuid import UUID
from typing import Optional
from sqlalchemy import select, func, or_, and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.entities.auth.usuario import Usuario, EstadoUsuario
from app.domain.exceptions import EmailYaRegistrado
from app.domain.ports.outbound.auth.repositorio_usuario import (
    RepositorioUsuario, FiltrosUsuario, PaginaUsuarios,
)
from app.infrastructure.persistence.modelos.auth.usuario_modelo import UsuarioModelo


def _encode_cursor(creado_en: datetime, id: UUID) -> str:
    data = json.dumps([creado_en.isoformat(), str(id)])
    return base64.urlsafe_b64encode(data.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    data = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
    dt = datetime.fromisoformat(data[0])
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt, UUID(data[1])


class UsuarioRepositorioSQL(RepositorioUsuario):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def guardar(self, usuario: Usuario, hash_password: str) -> Usuario:
        modelo = UsuarioModelo(
            id=usuario.id,
            public_id=usuario.public_id,
            email=usuario.email,
            nombre=usuario.nombre,
            apellido=usuario.apellido,
            hash_password=hash_password,
            estado=usuario.estado.value,
            email_verificado=usuario.email_verificado,
            creado_en=usuario.creado_en,
            actualizado_en=usuario.actualizado_en,
            organization_id=usuario.organization_id,
        )
        self._session.add(modelo)
        try:
            await self._session.flush()
        except IntegrityError:
            raise EmailYaRegistrado(f"El email '{usuario.email}' ya está registrado")
        return self._a_entidad(modelo)

    async def actualizar(self, usuario: Usuario) -> Usuario:
        modelo = await self._session.get(UsuarioModelo, usuario.id)
        if not modelo:
            raise ValueError(f"Usuario {usuario.id} no encontrado en BD")
        modelo.nombre = usuario.nombre
        modelo.apellido = usuario.apellido
        modelo.estado = usuario.estado.value
        modelo.email_verificado = usuario.email_verificado
        modelo.ultimo_login = usuario.ultimo_login
        modelo.actualizado_en = usuario.actualizado_en
        await self._session.flush()
        return self._a_entidad(modelo)

    async def buscar_por_id(self, id: UUID) -> Optional[Usuario]:
        modelo = await self._session.get(UsuarioModelo, id)
        return self._a_entidad(modelo) if modelo else None

    async def buscar_por_public_id(self, public_id: str) -> Optional[Usuario]:
        stmt = select(UsuarioModelo).where(UsuarioModelo.public_id == public_id)
        result = await self._session.execute(stmt)
        modelo = result.scalar_one_or_none()
        return self._a_entidad(modelo) if modelo else None

    async def buscar_por_email(self, email: str) -> Optional[Usuario]:
        stmt = select(UsuarioModelo).where(UsuarioModelo.email == email.lower())
        result = await self._session.execute(stmt)
        modelo = result.scalar_one_or_none()
        return self._a_entidad(modelo) if modelo else None

    async def obtener_hash_password(self, usuario_id: UUID) -> Optional[str]:
        stmt = select(UsuarioModelo.hash_password).where(UsuarioModelo.id == usuario_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def actualizar_password(self, usuario_id: UUID, nuevo_hash: str) -> None:
        modelo = await self._session.get(UsuarioModelo, usuario_id)
        if modelo:
            modelo.hash_password = nuevo_hash
            await self._session.flush()

    async def listar(self, filtros: FiltrosUsuario, organization_id=None) -> PaginaUsuarios:
        stmt = select(UsuarioModelo)

        # Filtro de tenant — obligatorio cuando multitenancy está habilitado
        if organization_id is not None:
            stmt = stmt.where(UsuarioModelo.organization_id == organization_id)

        if filtros.estado:
            stmt = stmt.where(UsuarioModelo.estado == filtros.estado.value)

        if filtros.busqueda:
            termino = f"%{filtros.busqueda}%"
            stmt = stmt.where(or_(
                UsuarioModelo.nombre.ilike(termino),
                UsuarioModelo.apellido.ilike(termino),
                UsuarioModelo.email.ilike(termino),
            ))

        if filtros.cursor:
            cursor_ts, cursor_id = _decode_cursor(filtros.cursor)
            stmt = stmt.where(or_(
                UsuarioModelo.creado_en < cursor_ts,
                and_(
                    UsuarioModelo.creado_en == cursor_ts,
                    UsuarioModelo.id < cursor_id,
                ),
            ))

        stmt = stmt.order_by(UsuarioModelo.creado_en.desc(), UsuarioModelo.id.desc())
        stmt = stmt.limit(filtros.tamanio + 1)
        modelos = list((await self._session.execute(stmt)).scalars().all())

        siguiente_cursor = None
        if len(modelos) > filtros.tamanio:
            modelos = modelos[:filtros.tamanio]
            ultimo = modelos[-1]
            siguiente_cursor = _encode_cursor(ultimo.creado_en, ultimo.id)

        return PaginaUsuarios(
            items=[self._a_entidad(m) for m in modelos],
            siguiente_cursor=siguiente_cursor,
            tamanio=filtros.tamanio,
        )

    async def existe_email(self, email: str) -> bool:
        stmt = select(func.count()).where(UsuarioModelo.email == email.lower())
        result = await self._session.execute(stmt)
        return result.scalar_one() > 0

    @staticmethod
    def _a_entidad(m: UsuarioModelo) -> Usuario:
        return Usuario(
            id=m.id,
            public_id=m.public_id,
            email=m.email,
            nombre=m.nombre,
            apellido=m.apellido,
            estado=EstadoUsuario(m.estado),
            email_verificado=m.email_verificado,
            ultimo_login=m.ultimo_login,
            creado_en=m.creado_en,
            actualizado_en=m.actualizado_en,
            organization_id=m.organization_id,
        )
