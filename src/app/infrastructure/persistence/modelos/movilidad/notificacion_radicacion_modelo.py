from datetime import datetime
from uuid import UUID as _UUID
from sqlalchemy import Boolean, DateTime, ForeignKey, Text, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.infrastructure.persistence.database import Base


class NotificacionRadicacionModelo(Base):
    __tablename__ = "mov_notificaciones_radicacion"

    id: Mapped[_UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    radicacion_id: Mapped[_UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mov_radicaciones.id", ondelete="CASCADE"),
        unique=True, nullable=False, index=True,
    )
    solicitante_notificado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notificado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)
    creado_por: Mapped[_UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True,
    )
    actualizado_por: Mapped[_UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True,
    )
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                server_default=text("NOW()"))
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                      server_default=text("NOW()"))
