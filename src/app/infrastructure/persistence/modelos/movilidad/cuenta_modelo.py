from datetime import datetime
from uuid import UUID as _UUID
from sqlalchemy import String, Boolean, DateTime, Enum as SAEnum, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.infrastructure.persistence.database import Base
from app.infrastructure.identity import uuid7, generar_public_id
from app.domain.entities.movilidad.cuenta import TipoServicio


class CuentaVehiculoModelo(Base):
    __tablename__ = "mov_cuentas_vehiculos"

    id: Mapped[_UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    public_id: Mapped[str] = mapped_column(
        String(35), unique=True, nullable=False, index=True,
        default=lambda: generar_public_id("cue"),
    )
    numero_cuenta: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True, index=True)
    placa: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    tipo_servicio: Mapped[str] = mapped_column(
        SAEnum(TipoServicio, name="tipo_servicio_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    propietario_nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    propietario_documento: Mapped[str] = mapped_column(String(30), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    organization_id: Mapped[_UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizaciones.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    creado_por: Mapped[_UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True,
    )

    __table_args__ = (
        Index("ix_mov_cuentas_org_placa", "organization_id", "placa"),
        Index("ix_mov_cuentas_activo", "activo"),
    )
