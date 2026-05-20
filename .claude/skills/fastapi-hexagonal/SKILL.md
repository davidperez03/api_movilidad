---
name: fastapi-hexagonal
description: Usa este skill cuando el usuario pida desarrollar APIs con Python y FastAPI, arquitectura hexagonal, APIs seguras, microservicios, estructura de proyecto backend, autenticación JWT, autorización por roles, middlewares de seguridad, o cualquier tarea de desarrollo backend en Python listo para producción.
---

# Skill: FastAPI con Arquitectura Hexagonal para Producción

Eres un experto en desarrollo backend con Python/FastAPI siguiendo arquitectura hexagonal (puertos y adaptadores). Tu objetivo es generar código **listo para entornos productivos reales**: robusto, seguro, testeable y mantenible.

## Principios Fundamentales

1. **Arquitectura Hexagonal** — El dominio no depende de frameworks ni infraestructura. FastAPI es un adaptador, no el núcleo.
2. **Seguridad por defecto** — Toda API expuesta es una superficie de ataque. Aplicar defensa en profundidad.
3. **Producción primero** — Sin atajos. Logging estructurado, manejo de errores, health checks, configuración por entorno.
4. **Código observable** — Trazabilidad, métricas, alertas. Si no se puede monitorear, no está listo.

---

## Estructura de Proyecto Estándar

```
src/
├── app/
│   ├── main.py                   # Punto de entrada FastAPI
│   ├── config.py                 # Configuración con pydantic-settings
│   ├── dependencies.py           # Inyección de dependencias global
│   │
│   ├── domain/                   # NÚCLEO — sin imports de frameworks
│   │   ├── entities/             # Entidades y Value Objects
│   │   ├── ports/                # Interfaces (puertos) de entrada y salida
│   │   │   ├── inbound/          # Casos de uso (interfaces)
│   │   │   └── outbound/         # Repositorios, servicios externos (interfaces)
│   │   ├── services/             # Servicios de dominio
│   │   └── exceptions.py         # Excepciones de dominio
│   │
│   ├── application/              # Casos de uso concretos
│   │   └── use_cases/
│   │
│   ├── infrastructure/           # Adaptadores de salida
│   │   ├── persistence/          # SQLAlchemy, repositorios concretos
│   │   ├── security/             # JWT, hashing, OAuth2
│   │   ├── messaging/            # Kafka, RabbitMQ, Redis
│   │   └── external/             # Clientes HTTP externos
│   │
│   └── api/                      # Adaptadores de entrada (FastAPI)
│       ├── v1/
│       │   ├── routers/          # Endpoints por dominio
│       │   ├── schemas/          # Request/Response Pydantic
│       │   └── middlewares/      # Auth, logging, rate limiting
│       └── error_handlers.py     # Manejo global de errores
│
├── tests/
│   ├── unit/                     # Tests de dominio y casos de uso
│   ├── integration/              # Tests con BD real (pytest + testcontainers)
│   └── e2e/                      # Tests end-to-end
│
├── alembic/                      # Migraciones de BD
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── pyproject.toml
└── .env.example
```

---

## Reglas de Arquitectura Hexagonal

### El Dominio es Puro
```python
# domain/entities/usuario.py — SIN imports de FastAPI, SQLAlchemy, etc.
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID
from uuid6 import uuid7
from enum import Enum

class RolUsuario(str, Enum):
    ADMIN = "admin"
    EDITOR = "editor"
    LECTOR = "lector"

@dataclass
class Usuario:
    email: str
    nombre: str
    rol: RolUsuario
    id: UUID = field(default_factory=uuid7)
    activo: bool = True
    creado_en: datetime = field(default_factory=datetime.utcnow)

    def puede_editar(self) -> bool:
        return self.rol in (RolUsuario.ADMIN, RolUsuario.EDITOR)

    def desactivar(self) -> None:
        if not self.activo:
            raise ValueError("El usuario ya está inactivo")
        self.activo = False
```

### Puertos (Interfaces)
```python
# domain/ports/outbound/repositorio_usuario.py
from abc import ABC, abstractmethod
from uuid import UUID
from typing import Optional, List
from app.domain.entities.usuario import Usuario

class RepositorioUsuario(ABC):

    @abstractmethod
    async def guardar(self, usuario: Usuario) -> Usuario: ...

    @abstractmethod
    async def buscar_por_id(self, id: UUID) -> Optional[Usuario]: ...

    @abstractmethod
    async def buscar_por_email(self, email: str) -> Optional[Usuario]: ...

    @abstractmethod
    async def listar_activos(self) -> List[Usuario]: ...
```

### Caso de Uso
```python
# application/use_cases/crear_usuario.py
from dataclasses import dataclass
from app.domain.entities.usuario import Usuario, RolUsuario
from app.domain.ports.outbound.repositorio_usuario import RepositorioUsuario
from app.domain.ports.outbound.servicio_hash import ServicioHash
from app.domain.exceptions import EmailYaRegistrado

@dataclass
class ComandoCrearUsuario:
    email: str
    nombre: str
    password: str
    rol: RolUsuario = RolUsuario.LECTOR

class CrearUsuarioUseCase:
    def __init__(
        self,
        repo: RepositorioUsuario,
        hash_service: ServicioHash,
    ):
        self._repo = repo
        self._hash = hash_service

    async def ejecutar(self, cmd: ComandoCrearUsuario) -> Usuario:
        existente = await self._repo.buscar_por_email(cmd.email)
        if existente:
            raise EmailYaRegistrado(f"El email {cmd.email} ya está registrado")

        usuario = Usuario(
            email=cmd.email,
            nombre=cmd.nombre,
            rol=cmd.rol,
        )
        # El hash de password se guarda en infraestructura, no en el dominio
        await self._repo.guardar_con_credencial(usuario, self._hash.hashear(cmd.password))
        return usuario
```

---

## Seguridad para Producción

### Configuración Segura
```python
# app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr, field_validator
from typing import List

class Configuracion(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    APP_NAME: str = "mi-api"
    APP_ENV: str = "production"
    DEBUG: bool = False
    ALLOWED_HOSTS: List[str] = ["*"]

    # Base de datos
    DATABASE_URL: SecretStr
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # JWT
    JWT_SECRET_KEY: SecretStr
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Seguridad
    BCRYPT_ROUNDS: int = 12
    RATE_LIMIT_PER_MINUTE: int = 60
    CORS_ORIGINS: List[str] = []

    @field_validator("APP_ENV")
    @classmethod
    def validar_entorno(cls, v: str) -> str:
        entornos_validos = {"development", "staging", "production"}
        if v not in entornos_validos:
            raise ValueError(f"APP_ENV debe ser uno de: {entornos_validos}")
        return v

config = Configuracion()
```

### JWT con Refresh Tokens
```python
# infrastructure/security/jwt_service.py
from datetime import datetime, timedelta, timezone
from uuid6 import uuid7
from jose import JWTError, jwt
from app.config import config
from app.domain.exceptions import TokenInvalido, TokenExpirado

class JWTService:

    def crear_access_token(self, payload: dict) -> str:
        datos = payload.copy()
        datos.update({
            "exp": datetime.now(timezone.utc) + timedelta(minutes=config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
            "iat": datetime.now(timezone.utc),
            "type": "access",
            "jti": str(uuid7()),
        })
        return jwt.encode(datos, config.JWT_SECRET_KEY.get_secret_value(), algorithm=config.JWT_ALGORITHM)

    def crear_refresh_token(self, user_id: str) -> str:
        datos = {
            "sub": user_id,
            "exp": datetime.now(timezone.utc) + timedelta(days=config.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
            "type": "refresh",
            "jti": str(uuid7()),
        }
        return jwt.encode(datos, config.JWT_SECRET_KEY.get_secret_value(), algorithm=config.JWT_ALGORITHM)

    def verificar_token(self, token: str, tipo: str = "access") -> dict:
        try:
            payload = jwt.decode(
                token,
                config.JWT_SECRET_KEY.get_secret_value(),
                algorithms=[config.JWT_ALGORITHM],
            )
            if payload.get("type") != tipo:
                raise TokenInvalido("Tipo de token incorrecto")
            return payload
        except JWTError as e:
            if "expired" in str(e):
                raise TokenExpirado("Token expirado")
            raise TokenInvalido(f"Token inválido: {e}")
```

### Middleware de Seguridad
```python
# api/v1/middlewares/security.py
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import time
import uuid

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Agrega headers de seguridad en todas las respuestas."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response

class RequestTracingMiddleware(BaseHTTPMiddleware):
    """Agrega correlation ID para trazabilidad distribuida."""

    async def dispatch(self, request: Request, call_next) -> Response:
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid7()))
        request.state.correlation_id = correlation_id
        start_time = time.perf_counter()

        response = await call_next(request)

        process_time = (time.perf_counter() - start_time) * 1000
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Process-Time-Ms"] = f"{process_time:.2f}"
        return response
```

---

## main.py para Producción

```python
# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import config
from app.api.v1.routers import auth, usuarios, documentos
from app.api.error_handlers import registrar_manejadores_error
from app.api.v1.middlewares.security import SecurityHeadersMiddleware, RequestTracingMiddleware
from app.infrastructure.persistence.database import init_db

limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicio
    await init_db()
    yield
    # Cierre limpio

def crear_app() -> FastAPI:
    app = FastAPI(
        title=config.APP_NAME,
        version="1.0.0",
        docs_url="/docs" if config.APP_ENV != "production" else None,
        redoc_url="/redoc" if config.APP_ENV != "production" else None,
        openapi_url="/openapi.json" if config.APP_ENV != "production" else None,
        lifespan=lifespan,
    )

    # Middlewares (orden importa — se aplican de afuera hacia adentro)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestTracingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*"],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=config.ALLOWED_HOSTS)

    # Rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Manejo de errores
    registrar_manejadores_error(app)

    # Routers
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["Autenticación"])
    app.include_router(usuarios.router, prefix="/api/v1/usuarios", tags=["Usuarios"])
    app.include_router(documentos.router, prefix="/api/v1/documentos", tags=["Documentos"])

    @app.get("/health", tags=["Salud"])
    async def health_check():
        return {"status": "ok", "entorno": config.APP_ENV}

    return app

app = crear_app()
```

---

## Manejo de Errores Global

```python
# api/error_handlers.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.domain.exceptions import (
    EntidadNoEncontrada, EmailYaRegistrado,
    TokenInvalido, TokenExpirado, PermisoDenegado
)
import logging

logger = logging.getLogger(__name__)

def registrar_manejadores_error(app: FastAPI) -> None:

    @app.exception_handler(EntidadNoEncontrada)
    async def no_encontrada(request: Request, exc: EntidadNoEncontrada):
        return JSONResponse(status_code=404, content={"detalle": str(exc)})

    @app.exception_handler(EmailYaRegistrado)
    async def email_duplicado(request: Request, exc: EmailYaRegistrado):
        return JSONResponse(status_code=409, content={"detalle": str(exc)})

    @app.exception_handler(TokenInvalido)
    async def token_invalido(request: Request, exc: TokenInvalido):
        return JSONResponse(status_code=401, content={"detalle": "Token inválido"})

    @app.exception_handler(TokenExpirado)
    async def token_expirado(request: Request, exc: TokenExpirado):
        return JSONResponse(status_code=401, content={"detalle": "Token expirado, renueva tu sesión"})

    @app.exception_handler(PermisoDenegado)
    async def permiso_denegado(request: Request, exc: PermisoDenegado):
        return JSONResponse(status_code=403, content={"detalle": "No tienes permiso para esta acción"})

    @app.exception_handler(Exception)
    async def error_generico(request: Request, exc: Exception):
        correlation_id = getattr(request.state, "correlation_id", "sin-id")
        logger.error(f"[{correlation_id}] Error inesperado: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detalle": "Error interno del servidor", "correlacion": correlation_id},
        )
```

---

## Dependencias de Inyección (FastAPI DI)

```python
# app/dependencies.py
from functools import lru_cache
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.repositorios.usuario_repo import UsuarioRepositorioSQL
from app.infrastructure.security.jwt_service import JWTService
from app.domain.entities.usuario import Usuario, RolUsuario

security = HTTPBearer()
jwt_service = JWTService()

async def get_usuario_actual(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_session),
) -> Usuario:
    payload = jwt_service.verificar_token(credentials.credentials)
    repo = UsuarioRepositorioSQL(session)
    usuario = await repo.buscar_por_id(payload["sub"])
    if not usuario or not usuario.activo:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado o inactivo")
    return usuario

def requiere_rol(*roles: RolUsuario):
    """Factory de dependencia para control de acceso basado en roles."""
    async def verificar_rol(usuario: Usuario = Depends(get_usuario_actual)) -> Usuario:
        if usuario.rol not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permiso insuficiente")
        return usuario
    return verificar_rol
```

---

## Instrucciones de Generación

Al generar código con este skill:

1. **Siempre respetar la separación de capas** — nunca importar SQLAlchemy o FastAPI en `domain/`.
2. **Generar archivos completos y funcionales**, no fragmentos. Si el usuario pide un endpoint, generar el router, schema, caso de uso, repositorio y entidad relacionados.
3. **Incluir tipos explícitos** en todo el código (`-> type`, `param: type`).
4. **Producción por defecto** — incluir logging, manejo de errores, validaciones y variables de entorno.
5. **Tests junto al código** — cuando se genera lógica, ofrecer el test unitario correspondiente.
6. **Proponer el `.env.example`** cuando se agreguen nuevas variables de configuración.
7. **No usar `print()`** — siempre `logging` con nivel apropiado.
8. **Passwords y secretos siempre con `SecretStr`** de pydantic, nunca como `str` plano.

Consultar los archivos de referencia para patrones avanzados:
- `references/seguridad-avanzada.md` — OAuth2, API Keys, 2FA
- `references/patrones-dominio.md` — Aggregates, Value Objects, Domain Events
- `references/infraestructura-produccion.md` — Docker, CI/CD, observabilidad
