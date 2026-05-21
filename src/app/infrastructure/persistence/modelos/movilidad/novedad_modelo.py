from datetime import datetime
from uuid import UUID as _UUID
from sqlalchemy import String, DateTime, Enum as SAEnum, ForeignKey, Index, Text, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.infrastructure.persistence.database import Base
from app.infrastructure.identity import uuid7, generar_public_id
from app.domain.entities.movilidad.novedad import TipoNovedad, PrioridadNovedad, EstadoNovedad


class NovedadModelo(Base):
    __tablename__ = "mov_novedades"

    id: Mapped[_UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    public_id: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True,
                                           default=lambda: generar_public_id("nov"))
    proceso_tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    proceso_id: Mapped[_UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    tipo_novedad: Mapped[str] = mapped_column(
        SAEnum(TipoNovedad, name="tipo_novedad_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    prioridad: Mapped[str] = mapped_column(
        SAEnum(PrioridadNovedad, name="prioridad_novedad_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False, default=PrioridadNovedad.MEDIA.value,
    )
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    estado: Mapped[str] = mapped_column(
        SAEnum(EstadoNovedad, name="estado_novedad_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False, default=EstadoNovedad.PENDIENTE.value,
    )
    solucion: Mapped[str | None] = mapped_column(Text, nullable=True)
    resuelto_por: Mapped[_UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True,
    )
    resuelto_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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

    __table_args__ = (
        Index("ix_mov_novedades_proceso", "proceso_tipo", "proceso_id"),
        Index("ix_mov_novedades_estado", "estado"),
    )
