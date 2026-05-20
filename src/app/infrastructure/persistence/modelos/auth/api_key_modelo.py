from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, ForeignKey, ARRAY, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.infrastructure.persistence.database import Base
from app.infrastructure.identity import uuid7, generar_public_id


class ApiKeyModelo(Base):
    __tablename__ = "api_keys"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    public_id: Mapped[str] = mapped_column(String(35), unique=True, nullable=False, index=True, default=lambda: generar_public_id("key"))
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    propietario_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    permisos: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    activa: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expira_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ultimo_uso: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
