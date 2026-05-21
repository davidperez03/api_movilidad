from datetime import datetime
from uuid import UUID as _UUID
from sqlalchemy import String, DateTime, Enum as SAEnum, ForeignKey, Index, Text, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.infrastructure.persistence.database import Base
from app.infrastructure.identity import uuid7, generar_public_id
from app.domain.entities.movilidad.radicacion import EstadoRadicacion


class RadicacionModelo(Base):
    __tablename__ = "mov_radicaciones"

    id: Mapped[_UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    public_id: Mapped[str] = mapped_column(
        String(35), unique=True, nullable=False, index=True,
        default=lambda: generar_public_id("rad"),
    )
    cuenta_id: Mapped[_UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mov_cuentas_vehiculos.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    traslado_id: Mapped[_UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mov_traslados.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    organismo_id: Mapped[_UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mov_organismos_transito.id", ondelete="RESTRICT"), nullable=False,
    )
    estado: Mapped[str] = mapped_column(
        SAEnum(EstadoRadicacion, name="estado_radicacion_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=EstadoRadicacion.SIN_ASIGNAR.value,
    )
    numero_radicado: Mapped[str | None] = mapped_column(String(100), nullable=True)
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)
    vence_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    organization_id: Mapped[_UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizaciones.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    creado_por: Mapped[_UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True,
    )
    asignado_a: Mapped[_UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True,
    )

    __table_args__ = (
        Index("ix_mov_radicaciones_estado", "estado"),
        Index("ix_mov_radicaciones_cuenta_estado", "cuenta_id", "estado"),
        Index("ix_mov_radicaciones_vence_en", "vence_en"),
    )
