from datetime import date, datetime
from uuid import UUID as _UUID
from sqlalchemy import String, Boolean, Date, DateTime, Enum as SAEnum, ForeignKey, Index, Integer, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.infrastructure.persistence.database import Base
from app.infrastructure.identity import uuid7, generar_public_id
from app.domain.entities.parqueadero.vehiculo import TipoVehiculoParqueadero


class VehiculoParqueaderoModelo(Base):
    __tablename__ = "parq_vehiculos"

    id: Mapped[_UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    public_id: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True,
                                           default=lambda: generar_public_id("veh"))
    placa: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)
    marca: Mapped[str] = mapped_column(String(100), nullable=False, server_default=text("''"))
    modelo: Mapped[str] = mapped_column(String(100), nullable=False, server_default=text("''"))
    tipo_vehiculo: Mapped[str] = mapped_column(
        SAEnum(TipoVehiculoParqueadero, name="tipo_vehiculo_parqueadero_enum",
               values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    soat_aseguradora: Mapped[str | None] = mapped_column(String(200), nullable=True)
    soat_vencimiento: Mapped[date | None] = mapped_column(Date, nullable=True)
    tecnomecanica_vencimiento: Mapped[date | None] = mapped_column(Date, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
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

    __table_args__ = (
        Index("ix_parq_veh_activo", "activo"),
    )
