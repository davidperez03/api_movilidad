import collections
import math
import os
from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr, field_validator
from typing import List, Optional, FrozenSet

# Busca el .env desde la raíz del proyecto (sube desde src/app/)
_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _ROOT / ".env"

# Whitelist de permisos válidos del sistema.
# Las API Keys solo pueden solicitar permisos de esta lista.
PERMISOS_SISTEMA: FrozenSet[str] = frozenset({
    "usuarios:crear",
    "usuarios:leer",
    "usuarios:editar",
    "usuarios:eliminar",
    "usuarios:suspender",
    "roles:crear",
    "roles:leer",
    "roles:editar",
    "roles:eliminar",
    "roles:asignar",
    "permisos:leer",
    "permisos:editar",
    "api_keys:crear",
    "api_keys:leer",
    "api_keys:revocar",
    "auditoria:leer",
    "auditoria:exportar",
    # Movilidad — clave = recurso:accion (igual que seed migración 002)
    "movilidad.cuentas:crear",
    "movilidad.cuentas:leer",
    "movilidad.cuentas:editar",
    "movilidad.traslados:crear",
    "movilidad.traslados:leer",
    "movilidad.traslados:aprobar",
    "movilidad.radicaciones:crear",
    "movilidad.radicaciones:leer",
    "movilidad.radicaciones:revisar",
    "movilidad.novedades:crear",
    "movilidad.novedades:resolver",
    "movilidad.reportes:leer",
    "movilidad.reportes:exportar",
    # Parqueadero
    "parqueadero.vehiculos:gestionar",
    "parqueadero.personal:gestionar",
    "parqueadero.inspecciones:crear",
    "parqueadero.inspecciones:aprobar",
    "parqueadero.reportes:leer",
    # NUNC
    "nunc.sesiones:crear",
    "nunc.registros:crear",
    "nunc.reportes:leer",
})


def _entropia(s: str) -> float:
    freq = collections.Counter(s)
    total = len(s)
    return -sum((c / total) * math.log2(c / total) for c in freq.values())


class Configuracion(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    APP_NAME: str = "users-api"
    APP_ENV: str = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # Supabase / PostgreSQL
    DATABASE_URL: SecretStr
    DATABASE_URL_DIRECT: Optional[SecretStr] = None
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_POOL_RECYCLE: int = 1800
    DATABASE_STATEMENT_TIMEOUT_MS: int = 30000

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_POOL_SIZE: int = 20
    TOKEN_BLACKLIST_TTL: int = 86400
    PERMISSIONS_CACHE_TTL: int = 300
    PERMISSIONS_LOCAL_CACHE_TTL: int = 30
    PERM_LOCAL_CACHE_MAX: int = 1000
    USUARIO_PERFIL_CACHE_TTL: int = 60
    IDEMPOTENCY_TTL: int = 86400
    IDEMPOTENCY_AUTO_TTL: int = 10
    IDEMPOTENCY_IN_FLIGHT_TTL: int = 30
    IDEMPOTENCY_MAX_BODY_CACHE_KB: int = 100

    # JWT
    JWT_SECRET_KEY: SecretStr
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    INACTIVIDAD_TIMEOUT_MINUTOS: int = 30

    # HMAC — firma service-to-service
    HMAC_SIGNING_SECRET: Optional[SecretStr] = None
    HMAC_REPLAY_WINDOW_SECONDS: int = 300

    # Seguridad
    BCRYPT_ROUNDS: int = 12
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_AUTH_PER_MINUTE: int = 10
    CORS_ORIGINS: List[str] = []
    ALLOWED_HOSTS: List[str] = ["*"]

    # Observabilidad
    METRICS_SECRET: str = ""

    # Multi-tenancy
    MULTITENANCY_ENABLED: bool = False

    # Auditoría
    AUDIT_ENABLED: bool = True
    AUDIT_EXCLUDE_PATHS: List[str] = ["/health", "/ready", "/docs", "/redoc", "/openapi.json"]

    # Login — política de bloqueo y timing
    LOGIN_LOCKOUT_MAX_INTENTOS: int = 10
    LOGIN_LOCKOUT_TTL: int = 900
    LOGIN_MIN_RESPONSE_SECS: float = 0.30

    # Paginación
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # Límites de requests
    MAX_REQUEST_BODY_SIZE: int = 10 * 1024 * 1024

    # API Keys
    API_KEY_USO_THROTTLE_SECONDS: int = 60

    # SMTP / Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASS: SecretStr = SecretStr("")
    SMTP_FROM: str = ""
    SMTP_TLS: bool = True
    EMAIL_VERIFICATION_TTL: int = 86400
    PASSWORD_RESET_TTL: int = 3600
    EMAIL_REENVIO_RATE_TTL: int = 300
    FRONTEND_URL: str = "http://localhost:3000"

    @field_validator("APP_ENV")
    @classmethod
    def validar_entorno(cls, v: str) -> str:
        validos = {"development", "staging", "production"}
        if v not in validos:
            raise ValueError(f"APP_ENV debe ser uno de: {validos}")
        return v

    @field_validator("BCRYPT_ROUNDS")
    @classmethod
    def validar_bcrypt_rounds(cls, v: int) -> int:
        if v < 10 or v > 14:
            raise ValueError("BCRYPT_ROUNDS debe estar entre 10 y 14. Valor típico: 12")
        return v

    def validar_produccion(self) -> None:
        if self.APP_ENV != "production":
            return

        secretos_debiles = {"CAMBIA-ESTO", "dev-secret", "dev-hmac"}

        jwt_val = self.JWT_SECRET_KEY.get_secret_value()
        if any(s in jwt_val for s in secretos_debiles) or len(jwt_val) < 32:
            raise RuntimeError("JWT_SECRET_KEY inseguro para producción. Genera con: openssl rand -hex 32")
        if _entropia(jwt_val) < 3.5:
            raise RuntimeError("JWT_SECRET_KEY tiene entropía insuficiente. Genera con: openssl rand -hex 32")

        if self.HMAC_SIGNING_SECRET:
            hmac_val = self.HMAC_SIGNING_SECRET.get_secret_value()
            if any(s in hmac_val for s in secretos_debiles) or len(hmac_val) < 32:
                raise RuntimeError("HMAC_SIGNING_SECRET inseguro para producción. Genera con: openssl rand -hex 32")
            if _entropia(hmac_val) < 3.5:
                raise RuntimeError("HMAC_SIGNING_SECRET tiene entropía insuficiente. Genera con: openssl rand -hex 32")

        if self.METRICS_SECRET and (_entropia(self.METRICS_SECRET) < 3.5 or len(self.METRICS_SECRET) < 16):
            raise RuntimeError("METRICS_SECRET inseguro. Genera con: openssl rand -hex 16")

        if "*" in self.ALLOWED_HOSTS:
            raise RuntimeError("ALLOWED_HOSTS no puede contener '*' en producción")
        for origin in self.CORS_ORIGINS:
            if "localhost" in origin or "127.0.0.1" in origin:
                raise RuntimeError(
                    f"CORS_ORIGINS contiene origen localhost en producción: {origin}"
                )
        if self.BCRYPT_ROUNDS < 12:
            raise RuntimeError("BCRYPT_ROUNDS debe ser >= 12 en producción (dev puede usar 10)")


@lru_cache
def get_config() -> Configuracion:
    return Configuracion()


config = get_config()
