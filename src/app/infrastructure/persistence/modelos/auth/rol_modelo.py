from datetime import datetime
from uuid import UUID as _UUID
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Table, Column, text, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.infrastructure.persistence.database import Base
from app.infrastructure.identity import uuid7, generar_public_id

rol_permisos_tabla = Table(
    "rol_permisos",
    Base.metadata,
    Column("rol_id", UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permiso_id", UUID(as_uuid=True), ForeignKey("permisos.id", ondelete="CASCADE"), primary_key=True),
)


class PermisoModelo(Base):
    __tablename__ = "permisos"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    recurso: Mapped[str] = mapped_column(String(100), nullable=False)
    accion: Mapped[str] = mapped_column(String(100), nullable=False)
    descripcion: Mapped[str] = mapped_column(String(255), default="")
    roles: Mapped[list["RolModelo"]] = relationship(
        secondary=rol_permisos_tabla, back_populates="permisos"
    )

    __table_args__ = (
        UniqueConstraint("recurso", "accion", name="uq_permisos_recurso_accion"),
    )


class RolModelo(Base):
    __tablename__ = "roles"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    public_id: Mapped[str] = mapped_column(String(35), unique=True, nullable=False, index=True, default=lambda: generar_public_id("rol"))
    nombre: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    descripcion: Mapped[str] = mapped_column(String(255), default="")
    es_sistema: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    organization_id: Mapped[_UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizaciones.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    # selectin evita lazy loading en AsyncSession (DetachedInstanceError) y elimina N+1
    permisos: Mapped[list[PermisoModelo]] = relationship(
        secondary=rol_permisos_tabla, back_populates="roles", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("nombre", "organization_id", name="uq_roles_nombre_org"),
        Index("ix_roles_org_nombre", "organization_id", "nombre"),
    )


class UsuarioRolModelo(Base):
    __tablename__ = "usuario_roles"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    usuario_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rol_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )
    asignado_por_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    vigente_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    asignado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    rol: Mapped[RolModelo] = relationship("RolModelo", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("usuario_id", "rol_id", name="uq_usuario_roles_usuario_rol"),
    )
