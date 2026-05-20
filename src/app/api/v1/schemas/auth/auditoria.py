from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.entities.auth.auditoria import (
    CategoriaEvento,
    NivelEvento,
    ResultadoAuditoria,
    TipoActor,
)


class RegistroAuditoriaResponse(BaseModel):
    # ── Identidad ─────────────────────────────────────────────────────────────
    id:               UUID
    numero_secuencia: int | None
    timestamp:        datetime
    timestamp_unix_ms: int
    correlation_id:   str

    # ── Actor ─────────────────────────────────────────────────────────────────
    actor_id:         UUID | None
    actor_email:      str | None
    actor_ip:         str
    actor_user_agent: str
    actor_tipo:       TipoActor
    sesion_id:        str | None
    api_key_id:       UUID | None

    # ── Clasificación ─────────────────────────────────────────────────────────
    categoria: CategoriaEvento
    nivel:     NivelEvento

    # ── Evento ────────────────────────────────────────────────────────────────
    accion:           str
    resultado:        ResultadoAuditoria
    resultado_detalle: str | None

    # ── Contexto HTTP ─────────────────────────────────────────────────────────
    metodo_http:      str
    path:             str
    query_params:     dict | None
    codigo_respuesta: int | None
    duracion_ms:      int | None

    # ── Recurso ───────────────────────────────────────────────────────────────
    recurso_tipo:   str
    recurso_id:     str | None
    valor_anterior: dict | None
    valor_nuevo:    dict | None
    diferencia:     dict | None

    # ── Extras ────────────────────────────────────────────────────────────────
    metadatos:    dict
    razon:        str | None
    error_mensaje: str | None

    # ── Integridad ────────────────────────────────────────────────────────────
    hash_registro: str
    firma_hmac:    str

    model_config = {"from_attributes": True}


class PaginaAuditoriaResponse(BaseModel):
    items:           list[RegistroAuditoriaResponse]
    total:           int
    tamanio:         int
    siguiente_cursor: str | None
    tiene_siguiente: bool


class EstadisticasAuditoriaResponse(BaseModel):
    total_eventos:                int
    por_categoria:                dict[str, int]
    por_nivel:                    dict[str, int]
    por_resultado:                dict[str, int]
    eventos_seguridad_24h:        int
    eventos_criticos_24h:         int
    intentos_fallidos_login_24h:  int
    periodo_desde:                datetime
    periodo_hasta:                datetime


class ResultadoVerificacionResponse(BaseModel):
    total_verificados: int
    total_ok:          int
    total_fallidos:    int
    total_sin_firma:   int = Field(description="Registros de trigger BD — no firmados por diseño")
    integro:           bool
    ids_fallidos:      list[UUID]
    verificado_en:     datetime
