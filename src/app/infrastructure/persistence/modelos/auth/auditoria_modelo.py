from datetime import datetime
from uuid import UUID as _UUID

from sqlalchemy import BigInteger, Index, Integer, String, DateTime, Enum as SAEnum, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.infrastructure.persistence.database import Base
from app.infrastructure.identity import uuid7
from app.domain.entities.auth.auditoria import (
    CategoriaEvento,
    NivelEvento,
    ResultadoAuditoria,
    TipoActor,
)


class AuditoriaModelo(Base):
    __tablename__ = "auditoria"

    # ── Identidad ─────────────────────────────────────────────────────────────
    id: Mapped[_UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)

    # numero_secuencia: BIGSERIAL asignado por PostgreSQL — mantiene orden total
    # incluso cuando dos registros tienen el mismo timestamp.
    numero_secuencia: Mapped[int] = mapped_column(
        BigInteger,
        server_default=text("nextval('auditoria_secuencia_seq')"),
        nullable=False,
        index=True,
    )

    # ── Tiempo ────────────────────────────────────────────────────────────────
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    # Milisegundos Unix — precisión sub-segundo, ordenable sin parsear datetime
    timestamp_unix_ms: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("(EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT"),
    )

    # ── Trazabilidad ──────────────────────────────────────────────────────────
    correlation_id: Mapped[str] = mapped_column(String(100), nullable=False, default="")

    # ── Actor ─────────────────────────────────────────────────────────────────
    actor_id:         Mapped[_UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    actor_email:      Mapped[str | None]   = mapped_column(String(255), nullable=True)
    actor_ip:         Mapped[str]          = mapped_column(String(45),  nullable=False, default="")
    actor_user_agent: Mapped[str]          = mapped_column(String(500), nullable=False, default="")
    actor_tipo: Mapped[str] = mapped_column(
        SAEnum(TipoActor, name="tipo_actor_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    sesion_id:   Mapped[str | None]   = mapped_column(String(100), nullable=True)
    api_key_id:  Mapped[_UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # ── Clasificación del evento ───────────────────────────────────────────────
    categoria: Mapped[str] = mapped_column(
        SAEnum(CategoriaEvento, name="categoria_evento_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        server_default="sistema",
    )
    nivel: Mapped[str] = mapped_column(
        SAEnum(NivelEvento, name="nivel_evento_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        server_default="info",
    )

    # ── Evento ────────────────────────────────────────────────────────────────
    accion: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    resultado: Mapped[str] = mapped_column(
        SAEnum(ResultadoAuditoria, name="resultado_auditoria_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    resultado_detalle: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # ── Contexto HTTP ─────────────────────────────────────────────────────────
    metodo_http:      Mapped[str]      = mapped_column(String(10),  nullable=False, server_default="")
    path:             Mapped[str]      = mapped_column(String(500), nullable=False, server_default="")
    query_params:     Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    codigo_respuesta: Mapped[int | None]  = mapped_column(Integer, nullable=True)
    duracion_ms:      Mapped[int | None]  = mapped_column(Integer, nullable=True)

    # ── Recurso afectado ──────────────────────────────────────────────────────
    recurso_tipo: Mapped[str]          = mapped_column(String(100), nullable=False)
    recurso_id:   Mapped[str | None]   = mapped_column(String(100), nullable=True)
    valor_anterior: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    valor_nuevo:    Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    diferencia:     Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ── Contexto adicional ────────────────────────────────────────────────────
    metadatos:     Mapped[dict]        = mapped_column(JSONB, nullable=False, default=dict)
    razon:         Mapped[str | None]  = mapped_column(String(500),  nullable=True)
    error_mensaje: Mapped[str | None]  = mapped_column(String(1000), nullable=True)

    # ── Multi-tenancy ─────────────────────────────────────────────────────────
    organization_id: Mapped[_UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizaciones.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Integridad / cadena de custodia ───────────────────────────────────────
    # Vacíos en registros de trigger BD — solo se firman los del middleware.
    hash_registro: Mapped[str] = mapped_column(String(64),  nullable=False, server_default="")
    firma_hmac:    Mapped[str] = mapped_column(String(100), nullable=False, server_default="")

    # ── Índices ───────────────────────────────────────────────────────────────
    __table_args__ = (
        # Búsquedas por actor — columna más selectiva primero
        Index("ix_aud_actor_ts",        "actor_id",    "timestamp"),
        Index("ix_aud_actor_ip_ts",     "actor_ip",    "timestamp"),
        Index("ix_aud_sesion_ts",       "sesion_id",   "timestamp"),
        # Búsquedas por recurso
        Index("ix_aud_recurso",         "recurso_tipo", "recurso_id", "timestamp"),
        # Búsquedas por evento
        Index("ix_aud_accion_ts",       "accion",      "timestamp"),
        Index("ix_aud_categoria_ts",    "categoria",   "timestamp"),
        Index("ix_aud_nivel_ts",        "nivel",       "timestamp"),
        Index("ix_aud_resultado_ts",    "resultado",   "timestamp"),
        # Timestamp global — usado en paginación por cursor
        Index("ix_aud_timestamp",       "timestamp"),
        # Multi-tenancy — siempre primera condición cuando está habilitado
        Index("ix_aud_org_ts",          "organization_id", "timestamp"),
        Index("ix_aud_org_categoria",   "organization_id", "categoria", "timestamp"),
        # Verificación de integridad — orden exacto de inserción
        Index("ix_aud_secuencia",       "numero_secuencia"),
    )
