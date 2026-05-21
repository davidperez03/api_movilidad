from datetime import datetime
from uuid import UUID as _UUID
from sqlalchemy import String, DateTime, Enum as SAEnum, ForeignKey, Index, Integer, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.infrastructure.persistence.database import Base
from app.infrastructure.identity import uuid7, generar_public_id
from app.domain.entities.nunc.sesion import EstadoSesionNunc


class SesionNuncModelo(Base):
    __tablename__ = "nunc_sesiones"

    id: Mapped[_UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    public_id: Mapped[str] = mapped_column(
        String(35), unique=True, nullable=False, index=True,
        default=lambda: generar_public_id("nunc"),
    )
    codigo: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    estado: Mapped[str] = mapped_column(
        SAEnum(EstadoSesionNunc, name="estado_sesion_nunc_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=EstadoSesionNunc.ACTIVA.value,
    )
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cerrado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    organization_id: Mapped[_UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizaciones.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    creado_por: Mapped[_UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False,
    )

    __table_args__ = (
        Index("ix_nunc_sesiones_estado", "estado"),
        Index("ix_nunc_sesiones_expira_en", "expira_en"),
    )


class RegistroNuncModelo(Base):
    __tablename__ = "nunc_registros"

    id: Mapped[_UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    public_id: Mapped[str] = mapped_column(
        String(35), unique=True, nullable=False, index=True,
        default=lambda: generar_public_id("reg"),
    )
    sesion_id: Mapped[_UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nunc_sesiones.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    numero_secuencial: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    placa: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    nombre_conductor: Mapped[str] = mapped_column(String(200), nullable=False)
    documento_conductor: Mapped[str] = mapped_column(String(30), nullable=False)
    datos_forenses: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    organization_id: Mapped[_UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizaciones.id", ondelete="SET NULL"), nullable=True,
    )
    creado_por: Mapped[_UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True,
    )
