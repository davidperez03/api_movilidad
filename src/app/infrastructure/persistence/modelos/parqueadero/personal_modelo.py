from datetime import date, datetime
from uuid import UUID as _UUID
from sqlalchemy import String, Date, DateTime, ForeignKey, Text, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.infrastructure.persistence.database import Base
from app.infrastructure.identity import uuid7


class DatosPersonalModelo(Base):
    __tablename__ = "parq_datos_personal"

    id: Mapped[_UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    perfil_id: Mapped[_UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="CASCADE"),
        unique=True, nullable=False,
    )
    licencia_numero: Mapped[str | None] = mapped_column(String(50), nullable=True)
    licencia_categoria: Mapped[str | None] = mapped_column(String(5), nullable=True)
    licencia_vencimiento: Mapped[date | None] = mapped_column(Date, nullable=True)
    documento_tipo: Mapped[str | None] = mapped_column(String(5), nullable=True)
    documento_numero: Mapped[str | None] = mapped_column(String(50), nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(20), nullable=True)
    contacto_emergencia_nombre: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contacto_emergencia_telefono: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
    organization_id: Mapped[_UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizaciones.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                server_default=text("NOW()"))
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                     server_default=text("NOW()"))
