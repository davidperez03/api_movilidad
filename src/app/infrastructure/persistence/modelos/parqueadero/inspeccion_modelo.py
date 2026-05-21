from datetime import datetime
from uuid import UUID as _UUID
from sqlalchemy import String, Boolean, DateTime, Enum as SAEnum, ForeignKey, Index, Text, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.infrastructure.persistence.database import Base
from app.infrastructure.identity import uuid7, generar_public_id
from app.domain.entities.parqueadero.inspeccion import TurnoInspeccion


class InspeccionModelo(Base):
    __tablename__ = "parq_inspecciones"

    id: Mapped[_UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    public_id: Mapped[str] = mapped_column(
        String(35), unique=True, nullable=False, index=True,
        default=lambda: generar_public_id("ins"),
    )
    vehiculo_id: Mapped[_UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("parq_vehiculos.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    personal_id: Mapped[_UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("parq_datos_personal.id", ondelete="RESTRICT"), nullable=False,
    )
    turno: Mapped[str] = mapped_column(
        SAEnum(TurnoInspeccion, name="turno_inspeccion_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    es_apto: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    observaciones_generales: Mapped[str | None] = mapped_column(Text, nullable=True)
    fotos: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    aprobado_por: Mapped[_UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True,
    )
    aprobado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    organization_id: Mapped[_UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizaciones.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    creado_por: Mapped[_UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True,
    )

    __table_args__ = (
        Index("ix_parq_inspecciones_vehiculo", "vehiculo_id"),
        Index("ix_parq_inspecciones_es_apto", "es_apto"),
    )
