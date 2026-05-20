import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID
from uuid6 import uuid7
from enum import Enum
from typing import Any


class ResultadoAuditoria(str, Enum):
    EXITOSO  = "exitoso"
    FALLIDO  = "fallido"
    DENEGADO = "denegado"


class TipoActor(str, Enum):
    USUARIO = "usuario"
    API_KEY = "api_key"
    SISTEMA = "sistema"
    ANONIMO = "anonimo"


class CategoriaEvento(str, Enum):
    AUTH      = "auth"       # login, logout, refresh, reset, verificación email
    SEGURIDAD = "seguridad"  # intentos fallidos, tokens inválidos, rate limit, 403
    USUARIO   = "usuario"    # CRUD de usuarios
    ROL       = "rol"        # CRUD de roles y permisos
    API_KEY   = "api_key"    # creación, uso, revocación de API keys
    DATOS     = "datos"      # lectura/exportación de datos sensibles
    SISTEMA   = "sistema"    # startup, shutdown, triggers BD, configuración


class NivelEvento(str, Enum):
    INFO        = "info"        # Operación normal exitosa
    ADVERTENCIA = "advertencia" # Inusual pero no crítico (401, ops fallidas)
    CRITICO     = "critico"     # Alto impacto (exports, bajas masivas, config)
    SEGURIDAD   = "seguridad"   # Evento de seguridad (403, rate limit, token inválido)


@dataclass
class RegistroAuditoria:

    # ── Obligatorios ─────────────────────────────────────────────────────────
    accion:       str
    resultado:    ResultadoAuditoria
    recurso_tipo: str
    actor_tipo:   TipoActor

    # ── Clasificación ─────────────────────────────────────────────────────────
    # Defaults para compat con triggers que insertan directo a BD sin contexto HTTP
    categoria: CategoriaEvento = CategoriaEvento.SISTEMA
    nivel:     NivelEvento     = NivelEvento.INFO

    # ── Identidad del registro ────────────────────────────────────────────────
    id:               UUID     = field(default_factory=uuid7)
    timestamp:        datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    timestamp_unix_ms: int     = 0   # calculado en __post_init__ — precisión ms

    # ── Contexto HTTP ─────────────────────────────────────────────────────────
    metodo_http:      str                    = ""
    path:             str                    = ""
    query_params:     dict[str, Any] | None  = None
    codigo_respuesta: int | None             = None
    duracion_ms:      int | None             = None
    correlation_id:   str                    = ""

    # ── Actor ─────────────────────────────────────────────────────────────────
    actor_id:        UUID | None = None
    actor_email:     str | None  = None
    actor_ip:        str         = ""
    actor_user_agent: str        = ""
    sesion_id:       str | None  = None
    api_key_id:      UUID | None = None
    organization_id: UUID | None = None

    # ── Recurso afectado ──────────────────────────────────────────────────────
    recurso_id:     str | None             = None
    valor_anterior: dict[str, Any] | None  = None
    valor_nuevo:    dict[str, Any] | None  = None
    diferencia:     dict[str, Any] | None  = None   # diff calculado automáticamente

    # ── Detalle del resultado ─────────────────────────────────────────────────
    metadatos:        dict[str, Any] = field(default_factory=dict)
    razon:            str | None     = None
    resultado_detalle: str | None    = None
    error_mensaje:    str | None     = None

    # ── Integridad / cadena de custodia ───────────────────────────────────────
    # numero_secuencia: BIGSERIAL asignado por PostgreSQL al insertar
    numero_secuencia: int | None = None
    # hash_registro y firma_hmac son calculados por CadenaAuditoria antes de persistir.
    # Registros de trigger BD quedan con "" — se excluyen de la verificación de integridad.
    hash_registro: str = ""
    firma_hmac:    str = ""

    # ─────────────────────────────────────────────────────────────────────────

    def __post_init__(self) -> None:
        if not self.timestamp_unix_ms:
            self.timestamp_unix_ms = int(self.timestamp.timestamp() * 1000)

    def calcular_hash(self) -> str:
        """
        SHA-256 determinístico de los campos inmutables de negocio.
        Usado por CadenaAuditoria para firmar y por el endpoint de verificación
        para recomputar y comparar contra lo almacenado.
        """
        campos = "|".join([
            str(self.id),
            str(self.timestamp_unix_ms),
            str(self.actor_id or ""),
            self.actor_ip or "",
            self.actor_email or "",
            self.accion,
            self.resultado.value,
            self.recurso_tipo,
            str(self.recurso_id or ""),
            self.categoria.value,
            self.nivel.value,
            self.correlation_id or "",
            self.metodo_http or "",
            self.path or "",
            str(self.codigo_respuesta or ""),
        ])
        return hashlib.sha256(campos.encode("utf-8")).hexdigest()

    @staticmethod
    def calcular_diferencia(
        anterior: dict[str, Any] | None,
        nuevo:    dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        """Retorna solo los campos que cambiaron, con valor antes/después."""
        if not anterior or not nuevo:
            return None
        diff = {
            k: {"antes": anterior.get(k), "despues": nuevo.get(k)}
            for k in set(anterior) | set(nuevo)
            if anterior.get(k) != nuevo.get(k)
        }
        return diff or None
