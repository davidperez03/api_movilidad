# Seguridad Avanzada — FastAPI Producción

## OAuth2 con Password Flow + Refresh Token

```python
# api/v1/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.persistence.database import get_session
from app.infrastructure.security.jwt_service import JWTService
from app.infrastructure.security.hash_service import HashService
from app.infrastructure.persistence.repositorios.usuario_repo import UsuarioRepositorioSQL
from app.api.v1.schemas.auth import TokenRespuesta, RefreshRequest

router = APIRouter()
jwt_service = JWTService()
hash_service = HashService()

@router.post("/login", response_model=TokenRespuesta)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
):
    repo = UsuarioRepositorioSQL(session)
    usuario = await repo.buscar_por_email(form.username)

    if not usuario or not await repo.verificar_credencial(usuario.id, form.password, hash_service):
        # Tiempo constante para evitar timing attacks
        hash_service.hashear("dummy_para_tiempo_constante")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not usuario.activo:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cuenta desactivada")

    access_token = jwt_service.crear_access_token({"sub": str(usuario.id), "rol": usuario.rol})
    refresh_token = jwt_service.crear_refresh_token(str(usuario.id))

    return TokenRespuesta(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expira_en=1800,
    )

@router.post("/refresh", response_model=TokenRespuesta)
async def refresh(body: RefreshRequest, session: AsyncSession = Depends(get_session)):
    payload = jwt_service.verificar_token(body.refresh_token, tipo="refresh")
    repo = UsuarioRepositorioSQL(session)
    usuario = await repo.buscar_por_id(payload["sub"])

    if not usuario or not usuario.activo:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario inválido")

    nuevo_access = jwt_service.crear_access_token({"sub": str(usuario.id), "rol": usuario.rol})
    return TokenRespuesta(
        access_token=nuevo_access,
        refresh_token=body.refresh_token,
        token_type="bearer",
        expira_en=1800,
    )

@router.post("/logout")
async def logout():
    # En producción: agregar el JTI del token a una blocklist en Redis
    return {"mensaje": "Sesión cerrada"}
```

---

## API Keys para Servicios Externos

```python
# infrastructure/security/api_key_service.py
import secrets
import hashlib
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.entities.api_key import APIKey

class APIKeyService:

    def generar_clave(self) -> tuple[str, str]:
        """Retorna (clave_plana, hash_almacenar)"""
        clave = f"sk_{secrets.token_urlsafe(32)}"
        hash_clave = hashlib.sha256(clave.encode()).hexdigest()
        return clave, hash_clave

    def verificar_clave(self, clave_plana: str, hash_almacenado: str) -> bool:
        hash_recibido = hashlib.sha256(clave_plana.encode()).hexdigest()
        return secrets.compare_digest(hash_recibido, hash_almacenado)

# Dependencia FastAPI para endpoints que aceptan API Keys
from fastapi import Security
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verificar_api_key(
    api_key: str = Security(api_key_header),
    session: AsyncSession = Depends(get_session),
):
    if not api_key:
        raise HTTPException(status_code=403, detail="API Key requerida")
    # Buscar en BD y verificar hash
    ...
```

---

## Rate Limiting por Usuario

```python
# api/v1/middlewares/rate_limit.py
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request

def get_user_identifier(request: Request) -> str:
    """Usa el ID de usuario autenticado, si no, la IP."""
    user = getattr(request.state, "usuario", None)
    if user:
        return str(user.id)
    return get_remote_address(request)

limiter = Limiter(key_func=get_user_identifier)

# Uso en endpoints:
# @router.post("/documentos")
# @limiter.limit("10/minute")
# async def crear_documento(request: Request, ...):
```

---

## Validación y Sanitización de Inputs

```python
# api/v1/schemas/base.py
from pydantic import BaseModel, field_validator, model_validator
import re
import html

class EsquemaBase(BaseModel):
    """Esquema base con sanitización automática."""

    @model_validator(mode="before")
    @classmethod
    def sanitizar_strings(cls, values: dict) -> dict:
        for campo, valor in values.items():
            if isinstance(valor, str):
                # Eliminar caracteres de control y escapar HTML
                valor = html.escape(valor.strip())
                # Eliminar null bytes
                valor = valor.replace("\x00", "")
                values[campo] = valor
        return values

class CrearDocumentoSchema(EsquemaBase):
    titulo: str
    contenido: str
    etiquetas: list[str] = []

    @field_validator("titulo")
    @classmethod
    def validar_titulo(cls, v: str) -> str:
        if len(v) < 3:
            raise ValueError("El título debe tener al menos 3 caracteres")
        if len(v) > 200:
            raise ValueError("El título no puede superar 200 caracteres")
        # Sin caracteres especiales peligrosos
        if re.search(r'[<>"\';]', v):
            raise ValueError("El título contiene caracteres no permitidos")
        return v
```

---

## Protección contra SQL Injection (con SQLAlchemy async)

```python
# infrastructure/persistence/repositorios/usuario_repo.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.domain.entities.usuario import Usuario
from app.infrastructure.persistence.models import UsuarioModel

class UsuarioRepositorioSQL:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def buscar_por_email(self, email: str) -> Usuario | None:
        # NUNCA usar string interpolation. Siempre parámetros vinculados.
        stmt = select(UsuarioModel).where(
            and_(UsuarioModel.email == email, UsuarioModel.activo == True)
        )
        resultado = await self._session.execute(stmt)
        modelo = resultado.scalar_one_or_none()
        return modelo.to_domain() if modelo else None
```

---

## CORS Restrictivo para Producción

```python
# En config.py — variable de entorno por separado por entorno
# .env.production
# CORS_ORIGINS=["https://app.midominio.com","https://admin.midominio.com"]

# En main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,      # Nunca "*" en producción
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Correlation-ID"],
    expose_headers=["X-Correlation-ID", "X-Process-Time-Ms"],
    max_age=600,
)
```

---

## Logging Estructurado (JSON para producción)

```python
# app/logging_config.py
import logging
import json
from datetime import datetime, timezone

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "nivel": record.levelname,
            "modulo": record.module,
            "mensaje": record.getMessage(),
        }
        if record.exc_info:
            log_data["excepcion"] = self.formatException(record.exc_info)
        if hasattr(record, "correlation_id"):
            log_data["correlation_id"] = record.correlation_id
        return json.dumps(log_data, ensure_ascii=False)

def configurar_logging(entorno: str) -> None:
    handler = logging.StreamHandler()
    if entorno == "production":
        handler.setFormatter(JSONFormatter())
        nivel = logging.INFO
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        nivel = logging.DEBUG

    logging.basicConfig(level=nivel, handlers=[handler])
    # Silenciar logs verbosos de librerías
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
```
