from datetime import datetime
from uuid import UUID as _UUID
from sqlalchemy import String, Boolean, DateTime, Index, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR
from app.infrastructure.persistence.database import Base
from app.infrastructure.identity import uuid7, generar_public_id


class OrganismoTransitoModelo(Base):
    __tablename__ = "mov_organismos_transito"

    id: Mapped[_UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    public_id: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True,
                                           default=lambda: generar_public_id("org"))
    nombre: Mapped[str] = mapped_column(String(300), nullable=False)
    tipo: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    municipio: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    departamento: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    telefono: Mapped[str | None] = mapped_column(String(50), nullable=True)
    direccion: Mapped[str | None] = mapped_column(String(500), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                server_default=text("NOW()"))
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                      server_default=text("NOW()"))

    __table_args__ = (
        Index("ix_mov_org_nombre2", "nombre"),
        Index("ix_mov_org_departamento2", "departamento"),
    )
