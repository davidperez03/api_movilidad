from datetime import date, time, datetime
from uuid import UUID as _UUID
from sqlalchemy import String, Boolean, Date, Time, DateTime, Enum as SAEnum, ForeignKey, Index, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.infrastructure.persistence.database import Base
from app.infrastructure.identity import uuid7, generar_public_id
from app.domain.entities.parqueadero.inspeccion import TurnoInspeccion


class InspeccionModelo(Base):
    __tablename__ = "parq_inspecciones"

    id: Mapped[_UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    public_id: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True,
                                           default=lambda: generar_public_id("ins"))
    codigo: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    vehiculo_id: Mapped[_UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("parq_vehiculos.id", ondelete="RESTRICT"), nullable=False, index=True,
    )
    operador_id: Mapped[_UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False,
    )
    auxiliar_id: Mapped[_UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True,
    )
    inspector_id: Mapped[_UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False,
    )
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    hora: Mapped[time] = mapped_column(Time, nullable=False)
    turno: Mapped[str] = mapped_column(
        SAEnum(TurnoInspeccion, name="turno_inspeccion_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    es_apto: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)
    firma_operador: Mapped[str | None] = mapped_column(Text, nullable=True)
    firma_inspector: Mapped[str | None] = mapped_column(Text, nullable=True)
    fotos: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    soat_vencimiento_snap: Mapped[date | None] = mapped_column(Date, nullable=True)
    tecnomecanica_vencimiento_snap: Mapped[date | None] = mapped_column(Date, nullable=True)
    licencia_vencimiento_snap: Mapped[date | None] = mapped_column(Date, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                server_default=text("NOW()"))
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                     server_default=text("NOW()"))
    organization_id: Mapped[_UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizaciones.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    creado_por: Mapped[_UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True,
    )
    actualizado_por: Mapped[_UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True,
    )

    __table_args__ = (
        Index("ix_parq_insp_fecha", "fecha"),
        Index("ix_parq_insp_operador", "operador_id"),
    )
