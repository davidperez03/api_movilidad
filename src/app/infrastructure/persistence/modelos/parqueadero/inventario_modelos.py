from datetime import date, datetime
from uuid import UUID as _UUID
from sqlalchemy import String, Boolean, Integer, Text, Date, DateTime, Enum as SAEnum, ForeignKey, UniqueConstraint, CheckConstraint, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.infrastructure.persistence.database import Base
from app.infrastructure.identity import uuid7, generar_public_id


class InsumoModelo(Base):
    __tablename__ = "inv_insumos"

    id: Mapped[_UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    public_id: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True,
                                           default=lambda: generar_public_id("ins"))
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    categoria: Mapped[str] = mapped_column(Text, nullable=False)
    unidad: Mapped[str] = mapped_column(Text, nullable=False)
    stock_minimo: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tipo_tracking: Mapped[str] = mapped_column(
        SAEnum("ubicacion", "rango", name="tipo_tracking_enum"), nullable=False, default="ubicacion",
    )
    modulo: Mapped[str] = mapped_column(Text, nullable=False, default="parqueadero")
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    organization_id: Mapped[_UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizaciones.id", ondelete="SET NULL"), nullable=True,
    )
    creado_por: Mapped[_UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True,
    )
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                server_default=text("NOW()"))
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                      server_default=text("NOW()"))


class StockModelo(Base):
    __tablename__ = "inv_stock"

    item_id: Mapped[_UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inv_insumos.id", ondelete="CASCADE"),
        primary_key=True, nullable=False,
    )
    modulo: Mapped[str] = mapped_column(Text, primary_key=True, nullable=False)
    ubicacion: Mapped[str] = mapped_column(Text, primary_key=True, nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  server_default=text("NOW()"))


class RangoModelo(Base):
    __tablename__ = "inv_rangos"

    id: Mapped[_UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    item_id: Mapped[_UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inv_insumos.id", ondelete="CASCADE"),
        unique=True, nullable=False,
    )
    rango_inicio: Mapped[int] = mapped_column(Integer, nullable=False)
    rango_fin: Mapped[int] = mapped_column(Integer, nullable=False)
    usados: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  server_default=text("NOW()"))
    updated_by: Mapped[_UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True,
    )


class MovimientoInventarioModelo(Base):
    __tablename__ = "inv_movimientos"

    id: Mapped[_UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    item_id: Mapped[_UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inv_insumos.id", ondelete="RESTRICT"), nullable=False,
    )
    modulo: Mapped[str] = mapped_column(Text, nullable=False)
    tipo: Mapped[str] = mapped_column(
        SAEnum("ingreso", "traslado", name="tipo_movimiento_enum"), nullable=False,
    )
    origen: Mapped[str | None] = mapped_column(Text, nullable=True)
    destino: Mapped[str] = mapped_column(Text, nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
    creado_por: Mapped[_UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True,
    )
    organization_id: Mapped[_UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizaciones.id", ondelete="SET NULL"), nullable=True,
    )
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                server_default=text("NOW()"))
    hash_anterior: Mapped[str | None] = mapped_column(Text, nullable=True)
    hash_registro: Mapped[str | None] = mapped_column(Text, nullable=True)


class CierreTurnoModelo(Base):
    __tablename__ = "parq_inv_cierres"

    id: Mapped[_UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    vehiculo_id: Mapped[_UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("parq_vehiculos.id", ondelete="RESTRICT"), nullable=False,
    )
    fecha: Mapped[date] = mapped_column(Date, nullable=False, server_default=text("current_date"))
    creado_por: Mapped[_UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True,
    )
    organization_id: Mapped[_UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizaciones.id", ondelete="SET NULL"), nullable=True,
    )
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                server_default=text("NOW()"))

    __table_args__ = (UniqueConstraint("vehiculo_id", "fecha", name="uq_parq_inv_cierre_vehiculo_fecha"),)


class CierreTurnoDetalleModelo(Base):
    __tablename__ = "parq_inv_cierres_detalle"

    id: Mapped[_UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    cierre_id: Mapped[_UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("parq_inv_cierres.id", ondelete="CASCADE"), nullable=False,
    )
    item_id: Mapped[_UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inv_insumos.id", ondelete="RESTRICT"), nullable=False,
    )
    cantidad_inicial: Mapped[int] = mapped_column(Integer, nullable=False)
    cantidad_final: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (UniqueConstraint("cierre_id", "item_id", name="uq_parq_cierre_detalle"),)
