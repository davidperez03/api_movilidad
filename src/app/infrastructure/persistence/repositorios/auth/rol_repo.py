from uuid import UUID
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.entities.auth.rol import Rol, Permiso, AsignacionRol
from app.domain.ports.outbound.auth.repositorio_rol import RepositorioRol
from app.domain.exceptions import ReglaDeNegocioViolada
from app.infrastructure.persistence.modelos.auth.rol_modelo import (
    RolModelo, PermisoModelo, UsuarioRolModelo,
)


class RolRepositorioSQL(RepositorioRol):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def guardar_rol(self, rol: Rol) -> Rol:
        modelo = RolModelo(
            id=rol.id,
            public_id=rol.public_id,
            nombre=rol.nombre.lower().strip(),
            descripcion=rol.descripcion,
            es_sistema=rol.es_sistema,
        )
        self._session.add(modelo)
        await self._session.flush()
        await self._session.refresh(modelo, ["permisos"])
        return self._rol_a_entidad(modelo)

    async def actualizar_rol(self, rol: Rol) -> Rol:
        stmt = (
            select(RolModelo)
            .where(RolModelo.id == rol.id)
            .options(selectinload(RolModelo.permisos))
        )
        result = await self._session.execute(stmt)
        modelo = result.scalar_one_or_none()
        if not modelo:
            raise ValueError(f"Rol {rol.id} no encontrado")
        modelo.nombre = rol.nombre.lower().strip()
        modelo.descripcion = rol.descripcion

        permisos_ids = {p.id for p in rol.permisos}
        modelos_permisos = []
        for pid in permisos_ids:
            pm = await self._session.get(PermisoModelo, pid)
            if pm:
                modelos_permisos.append(pm)
        modelo.permisos = modelos_permisos

        await self._session.flush()
        return self._rol_a_entidad(modelo)

    async def buscar_rol_por_id(self, id: UUID) -> Optional[Rol]:
        stmt = (
            select(RolModelo)
            .where(RolModelo.id == id)
            .options(selectinload(RolModelo.permisos))
        )
        result = await self._session.execute(stmt)
        modelo = result.scalar_one_or_none()
        return self._rol_a_entidad(modelo) if modelo else None

    async def buscar_rol_por_public_id(self, public_id: str) -> Optional[Rol]:
        stmt = (
            select(RolModelo)
            .where(RolModelo.public_id == public_id)
            .options(selectinload(RolModelo.permisos))
        )
        result = await self._session.execute(stmt)
        modelo = result.scalar_one_or_none()
        return self._rol_a_entidad(modelo) if modelo else None

    async def buscar_rol_por_nombre(self, nombre: str, organization_id=None) -> Optional[Rol]:
        """Busca primero en roles de sistema (globales), luego en roles del tenant."""
        from sqlalchemy import or_
        stmt = (
            select(RolModelo)
            .where(RolModelo.nombre == nombre.lower())
            .options(selectinload(RolModelo.permisos))
        )
        if organization_id is not None:
            stmt = stmt.where(
                or_(
                    RolModelo.organization_id.is_(None),
                    RolModelo.organization_id == organization_id,
                )
            )
        result = await self._session.execute(stmt)
        modelo = result.scalar_one_or_none()
        return self._rol_a_entidad(modelo) if modelo else None

    async def listar_roles(self, organization_id=None) -> list[Rol]:
        stmt = select(RolModelo).options(selectinload(RolModelo.permisos))

        if organization_id is not None:
            # Retornar roles del sistema (globales) + roles propios del tenant
            from sqlalchemy import or_
            stmt = stmt.where(
                or_(
                    RolModelo.organization_id.is_(None),      # Roles de sistema (globales)
                    RolModelo.organization_id == organization_id,  # Roles del tenant
                )
            )

        result = await self._session.execute(stmt.order_by(RolModelo.nombre))
        return [self._rol_a_entidad(m) for m in result.scalars().all()]

    async def eliminar_rol(self, id: UUID) -> None:
        await self._session.execute(delete(RolModelo).where(RolModelo.id == id))

    async def guardar_permiso(self, permiso: Permiso) -> Permiso:
        modelo = PermisoModelo(
            id=permiso.id,
            recurso=permiso.recurso,
            accion=permiso.accion,
            descripcion=permiso.descripcion,
        )
        self._session.add(modelo)
        await self._session.flush()
        return permiso

    async def listar_permisos(self) -> list[Permiso]:
        stmt = select(PermisoModelo).order_by(PermisoModelo.recurso, PermisoModelo.accion)
        result = await self._session.execute(stmt)
        return [self._permiso_a_entidad(m) for m in result.scalars().all()]

    async def asignar_rol_a_usuario(self, asignacion: AsignacionRol) -> AsignacionRol:
        modelo = UsuarioRolModelo(
            id=asignacion.id,
            usuario_id=asignacion.usuario_id,
            rol_id=asignacion.rol_id,
            asignado_por_id=asignacion.asignado_por_id,
            vigente_hasta=asignacion.vigente_hasta,
        )
        self._session.add(modelo)
        try:
            await self._session.flush()
        except IntegrityError:
            raise ReglaDeNegocioViolada("El usuario ya tiene este rol asignado")
        return asignacion

    async def revocar_rol_de_usuario(self, usuario_id: UUID, rol_id: UUID) -> None:
        stmt = delete(UsuarioRolModelo).where(
            UsuarioRolModelo.usuario_id == usuario_id,
            UsuarioRolModelo.rol_id == rol_id,
        )
        await self._session.execute(stmt)

    async def obtener_roles_de_usuario(self, usuario_id: UUID) -> list[Rol]:
        ahora = datetime.now(timezone.utc)
        stmt = (
            select(UsuarioRolModelo)
            .where(
                UsuarioRolModelo.usuario_id == usuario_id,
                (UsuarioRolModelo.vigente_hasta == None) | (UsuarioRolModelo.vigente_hasta > ahora),
            )
            .options(
                joinedload(UsuarioRolModelo.rol).selectinload(RolModelo.permisos)
            )
        )
        result = await self._session.execute(stmt)
        asignaciones = result.scalars().unique().all()
        return [self._rol_a_entidad(a.rol) for a in asignaciones if a.rol]

    async def obtener_permisos_de_usuario(self, usuario_id: UUID) -> set[str]:
        roles = await self.obtener_roles_de_usuario(usuario_id)
        permisos: set[str] = set()
        for rol in roles:
            permisos.update(rol.obtener_claves_permisos())
        return permisos

    @staticmethod
    def _rol_a_entidad(m: RolModelo) -> Rol:
        rol = Rol(
            id=m.id,
            public_id=m.public_id,
            nombre=m.nombre,
            descripcion=m.descripcion,
            es_sistema=m.es_sistema,
            creado_en=m.creado_en,
            actualizado_en=m.actualizado_en,
        )
        for pm in (m.permisos or []):
            rol.permisos.add(RolRepositorioSQL._permiso_a_entidad(pm))
        return rol

    @staticmethod
    def _permiso_a_entidad(m: PermisoModelo) -> Permiso:
        return Permiso(id=m.id, recurso=m.recurso, accion=m.accion, descripcion=m.descripcion)
