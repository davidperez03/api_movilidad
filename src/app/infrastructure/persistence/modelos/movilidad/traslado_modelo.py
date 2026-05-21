from datetime import date, datetime
from uuid import UUID as _UUID
from sqlalchemy import String, Date, DateTime, Enum as SAEnum, ForeignKey, Index, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.infrastructure.persistence.database import Base
from app.infrastructure.identity import uuid7, generar_public_id
from app.domain.entities.movilidad.traslado import EstadoTraslado


class TrasladoModelo(Base):
    __tablename__ = "mov_traslados"

    id: Mapped[_UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    public_id: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True,
                                           default=lambda: generar_public_id("tra"))
    cuenta_id: Mapped[_UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mov_cuentas_vehiculos.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    organismo_destino_id: Mapped[_UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mov_organismos_transito.id", ondelete="SET NULL"), nullable=True,
    )
    empresa_transportadora_id: Mapped[_UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mov_empresas_transporte.id", ondelete="SET NULL"), nullable=True,
    )
    estado: Mapped[str] = mapped_column(
        SAEnum(EstadoTraslado, name="estado_traslado_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False, default=EstadoTraslado.SIN_ASIGNAR.value,
    )
    numero_guia: Mapped[str | None] = mapped_column(String(100), nullable=True)
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)
    aprobado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    vencimiento: Mapped[date | None] = mapped_column(Date, nullable=True)
    completado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
        Index("ix_mov_traslados_estado", "estado"),
        Index("ix_mov_traslados_vencimiento", "vencimiento"),
    )
