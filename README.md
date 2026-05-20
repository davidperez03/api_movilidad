# users-api

API enterprise de gestión de usuarios y autenticación. Arquitectura hexagonal, FastAPI, PostgreSQL (Supabase), Redis (Upstash), Vercel.

## Stack

| Capa | Tecnología |
|------|-----------|
| Framework | FastAPI 0.115 + Uvicorn |
| Base de datos | PostgreSQL 16 vía Supabase (asyncpg + SQLAlchemy 2.0) |
| Cache / Blacklist | Redis 7 vía Upstash |
| Auth | JWT (HS256) + HMAC para service-to-service |
| Hashing | bcrypt×12 (async, no bloquea event loop) |
| Migraciones | Alembic |
| Deploy | Vercel (serverless) |
| Observabilidad | Prometheus (`/metrics`) + JSON logging |

## Inicio rápido

```bash
# 1. Instalar dependencias
poetry install

# 2. Configurar entorno
cp .env.example .env
# Editar .env con tus credenciales de Supabase y Redis

# 3. Aplicar migraciones
alembic upgrade head

# 4. Correr en desarrollo
uvicorn src.app.main:app --reload --port 8000

# 5. Abrir docs
open http://localhost:8000/docs
```

## Docker

```bash
# Levantar todo (API + PostgreSQL + Redis)
docker compose -f docker/docker-compose.yml up

# Solo la API (asume Supabase/Upstash externos)
docker build -f docker/Dockerfile -t users-api .
docker run -p 8000:8000 --env-file .env users-api
```

## Tests

```bash
# Todos los tests unitarios
PYTHONPATH=src pytest tests/unit/ -v

# Con coverage
PYTHONPATH=src pytest tests/ --cov=src --cov-report=term-missing --cov-fail-under=70

# Solo integración (requiere Docker o DATABASE_URL configurada)
PYTHONPATH=src pytest tests/integration/ -v
```

## Endpoints principales

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/api/v1/auth/login` | Login con email/password |
| POST | `/api/v1/auth/refresh` | Renovar access token |
| POST | `/api/v1/auth/logout` | Revocar sesión |
| POST | `/api/v1/usuarios` | Crear usuario |
| GET | `/api/v1/usuarios` | Listar usuarios (paginación por cursor) |
| GET | `/api/v1/usuarios/me` | Perfil del usuario actual |
| GET | `/api/v1/roles` | Listar roles |
| POST | `/api/v1/roles/asignar` | Asignar rol a usuario |
| GET | `/api/v1/auditoria` | Historial de auditoría |
| GET | `/metrics?token=<secret>` | Métricas Prometheus |
| GET | `/health` | Health check |
| GET | `/ready` | Readiness probe (DB + Redis) |

## Variables de entorno necesarias

Ver `.env.example` para la lista completa. Las mínimas para arrancar:

```env
DATABASE_URL=postgresql://...
JWT_SECRET_KEY=<32+ chars>
REDIS_URL=redis://...
```

## Arquitectura

Ver [CLAUDE.md](CLAUDE.md) para la guía completa del codebase.

## Despliegue en producción

Ver [DEPLOYMENT.md](DEPLOYMENT.md) para el checklist de producción.
