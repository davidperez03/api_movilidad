from datetime import datetime
from uuid import UUID as _UUID
from sqlalchemy import String, DateTime, Enum as SAEnum, ForeignKey, Index, Integer, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.infrastructure.persistence.database import Base
from app.infrastructure.identity import uuid7, generar_public_id
from app.domain.entities.nunc.sesion import EstadoSesionNunc


class SesionNuncModelo(Base):
    __tablename__ = "nunc_sesiones"

    id: Mapped[_UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    public_id: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True,
                                           default=lambda: generar_public_id("nunc"))
    codigo_sesion: Mapped[str] = mapped_column(String(10), unique=True, nullable=False,
                                               server_default=text("''"))
    nombre_entidad: Mapped[str] = mapped_column(String(300), nullable=False)
    nombre_perito: Mapped[str] = mapped_column(String(300), nullable=False)
    departamento: Mapped[str] = mapped_column(String(10), nullable=False)
    municipio: Mapped[str] = mapped_column(String(10), nullable=False)
    entidad: Mapped[str] = mapped_column(String(10), nullable=False)
    unidad: Mapped[str] = mapped_column(String(10), nullable=False)
    ano: Mapped[str] = mapped_column(String(4), nullable=False)
    estado: Mapped[str] = mapped_column(
        SAEnum(EstadoSesionNunc, name="estado_sesion_nunc_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False, default=EstadoSesionNunc.ACTIVA.value,
    )
    expiracion: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cerrado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
        Index("ix_nunc_ses_codigo", "codigo_sesion"),
        Index("ix_nunc_ses_expiracion", "expiracion"),
    )


class RegistroNuncModelo(Base):
    __tablename__ = "nunc_registros"

    id: Mapped[_UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    public_id: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True,
                                           default=lambda: generar_public_id("reg"))
    sesion_id: Mapped[_UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nunc_sesiones.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    numero_secuencial: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    placa: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    departamento: Mapped[str] = mapped_column(String(10), nullable=False)
    municipio: Mapped[str] = mapped_column(String(10), nullable=False)
    entidad: Mapped[str] = mapped_column(String(10), nullable=False)
    unidad: Mapped[str] = mapped_column(String(10), nullable=False)
    ano: Mapped[str] = mapped_column(String(4), nullable=False)
    organization_id: Mapped[_UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizaciones.id", ondelete="SET NULL"), nullable=True,
    )
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                server_default=text("NOW()"))
