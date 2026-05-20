from datetime import datetime, timezone
from uuid import UUID as _UUID
from sqlalchemy import String, Boolean, DateTime, Enum as SAEnum, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.infrastructure.persistence.database import Base
from app.infrastructure.identity import uuid7, generar_public_id
from app.domain.entities.auth.usuario import EstadoUsuario


class UsuarioModelo(Base):
    __tablename__ = "usuarios"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    public_id: Mapped[str] = mapped_column(String(35), unique=True, nullable=False, index=True, default=lambda: generar_public_id("usr"))
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    apellido: Mapped[str] = mapped_column(String(100), nullable=False)
    hash_password: Mapped[str] = mapped_column(String(255), nullable=False)
    estado: Mapped[str] = mapped_column(
        SAEnum(
            EstadoUsuario,
            name="estado_usuario_enum",
            values_callable=lambda x: [e.value for e in x],  # asyncpg usa .name sin esto
        ),
        nullable=False,
        default=EstadoUsuario.PENDIENTE_VERIFICACION.value,
    )
    email_verificado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ultimo_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
    # Multi-tenancy: nullable para compatibilidad con datos existentes.
    # Cuando MULTITENANCY_ENABLED=True, todas las queries deben filtrar por este campo.
    organization_id: Mapped[_UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizaciones.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    __table_args__ = (
        Index("ix_usuarios_estado", "estado"),
        Index("ix_usuarios_creado_en", "creado_en"),
        Index("ix_usuarios_org_estado", "organization_id", "estado"),
    )
