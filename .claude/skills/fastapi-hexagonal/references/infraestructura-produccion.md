# Infraestructura para Producción

## Dockerfile Multi-stage

```dockerfile
# docker/Dockerfile
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# --- Dependencias ---
FROM base AS deps
COPY pyproject.toml ./
RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache $(python -c "import tomllib; d=tomllib.load(open('pyproject.toml','rb')); print(' '.join(d['project']['dependencies']))")

# --- Producción ---
FROM base AS production
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --shell /bin/sh --no-create-home appuser

COPY --from=deps /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY --from=deps /usr/local/bin /usr/local/bin
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./

RUN chown -R appuser:appgroup /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--no-access-log"]
```

---

## docker-compose para Desarrollo Local

```yaml
# docker/docker-compose.yml
version: "3.9"

services:
  api:
    build:
      context: ..
      dockerfile: docker/Dockerfile
      target: production
    ports:
      - "8000:8000"
    env_file: ../.env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - backend

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: ${DB_USER:-appuser}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-changeme}
      POSTGRES_DB: ${DB_NAME:-appdb}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-appuser}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - backend

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD:-changeme} --maxmemory 256mb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - backend

volumes:
  postgres_data:

networks:
  backend:
    driver: bridge
```

---

## pyproject.toml Completo

```toml
[project]
name = "mi-api"
version = "1.0.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "pydantic>=2.9.0",
    "pydantic-settings>=2.6.0",
    "sqlalchemy[asyncio]>=2.0.36",
    "asyncpg>=0.30.0",
    "alembic>=1.14.0",
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",
    "slowapi>=0.1.9",
    "redis>=5.2.0",
    "python-multipart>=0.0.18",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=6.0.0",
    "httpx>=0.28.0",
    "testcontainers[postgres]>=4.8.0",
    "ruff>=0.8.0",
    "mypy>=1.13.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "--cov=src --cov-report=term-missing --cov-fail-under=80"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "S", "B", "A"]
ignore = ["S101"]  # Permitir assert en tests

[tool.mypy]
python_version = "3.12"
strict = true
ignore_missing_imports = true
```

---

## Migraciones con Alembic (async)

```python
# alembic/env.py
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
from app.config import config as app_config
from app.infrastructure.persistence.models import Base

config = context.config
config.set_main_option("sqlalchemy.url", app_config.DATABASE_URL.get_secret_value())

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations():
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

def run_migrations_online():
    asyncio.run(run_async_migrations())

run_migrations_online()
```

---

## Health Check Detallado

```python
# api/v1/routers/health.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import redis.asyncio as redis_client
from app.infrastructure.persistence.database import get_session
from app.config import config

router = APIRouter()

@router.get("/health/live")
async def liveness():
    """Kubernetes liveness probe — ¿el proceso está vivo?"""
    return {"status": "ok"}

@router.get("/health/ready")
async def readiness(session: AsyncSession = Depends(get_session)):
    """Kubernetes readiness probe — ¿listo para recibir tráfico?"""
    chequeos = {}

    # Base de datos
    try:
        await session.execute(text("SELECT 1"))
        chequeos["base_datos"] = "ok"
    except Exception as e:
        chequeos["base_datos"] = f"error: {e}"

    # Redis
    try:
        r = redis_client.from_url(config.REDIS_URL.get_secret_value())
        await r.ping()
        await r.aclose()
        chequeos["redis"] = "ok"
    except Exception as e:
        chequeos["redis"] = f"error: {e}"

    todo_ok = all(v == "ok" for v in chequeos.values())
    return {
        "status": "ok" if todo_ok else "degradado",
        "chequeos": chequeos,
        "version": "1.0.0",
        "entorno": config.APP_ENV,
    }
```

---

## Configuración de Base de Datos Async

```python
# infrastructure/persistence/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import config

engine = create_async_engine(
    config.DATABASE_URL.get_secret_value(),
    pool_size=config.DATABASE_POOL_SIZE,
    max_overflow=config.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,          # Detecta conexiones muertas
    pool_recycle=3600,           # Recicla conexiones cada hora
    echo=config.DEBUG,           # SQL logging solo en desarrollo
)

SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

class Base(DeclarativeBase):
    pass

async def init_db() -> None:
    """Verificar conectividad al iniciar la aplicación."""
    async with engine.connect() as conn:
        from sqlalchemy import text
        await conn.execute(text("SELECT 1"))

async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

---

## CI/CD con GitHub Actions

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_PASSWORD: testpass
          POSTGRES_DB: testdb
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v4

      - name: Configurar Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"

      - name: Instalar dependencias
        run: pip install uv && uv pip install --system -e ".[dev]"

      - name: Linting
        run: ruff check src/ tests/

      - name: Type checking
        run: mypy src/

      - name: Tests
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:testpass@localhost/testdb
          JWT_SECRET_KEY: secreto-solo-para-tests-no-usar-en-prod
          APP_ENV: testing
        run: pytest --cov-report=xml

      - name: Subir cobertura
        uses: codecov/codecov-action@v4

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - name: Construir imagen Docker
        run: docker build -f docker/Dockerfile -t mi-api:${{ github.sha }} .
```

---

## Tests de Integración con Testcontainers

```python
# tests/integration/conftest.py
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from testcontainers.postgres import PostgresContainer
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.main import crear_app
from app.infrastructure.persistence.models import Base
from app.infrastructure.persistence.database import get_session

@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg

@pytest_asyncio.fixture(scope="session")
async def engine_prueba(postgres_container):
    url = postgres_container.get_connection_url().replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture
async def session_prueba(engine_prueba):
    Session = async_sessionmaker(engine_prueba, expire_on_commit=False)
    async with Session() as session:
        yield session
        await session.rollback()

@pytest_asyncio.fixture
async def cliente(session_prueba):
    app = crear_app()
    app.dependency_overrides[get_session] = lambda: session_prueba
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
```
