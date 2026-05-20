"""
Fixtures de integración con dos estrategias según el entorno:

  1. Docker disponible  → PostgreSQL en contenedor (testcontainers) — aislado y reproducible.
  2. Docker no disponible → BD real configurada en DATABASE_URL (Supabase/local) — rápido en dev.
  3. Ninguna disponible → tests skippeados automáticamente con mensaje claro.

Estrategia de aislamiento:
  - Cada test usa emails/IDs únicos (UUID), por lo que no necesita rollback entre tests.
  - La BD acumula datos de test; en CI usar contenedor Docker para BD limpia.

Para correr:
    pytest tests/integration/ -v
    pytest tests/integration/ -v -k "migraciones"
"""
import os
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker


# ─── Detección de estrategia ──────────────────────────────────────────────────

def _docker_disponible() -> bool:
    try:
        import docker
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


def _url_bd_real() -> str | None:
    try:
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
        from app.config import config
        url = config.DATABASE_URL.get_secret_value()
        return (
            url.replace("postgresql://", "postgresql+asyncpg://")
               .replace("postgres://", "postgresql+asyncpg://")
        )
    except Exception:
        return None


_USA_DOCKER = _docker_disponible()
_URL_BD_REAL = _url_bd_real()

if not _USA_DOCKER and not _URL_BD_REAL:
    pytest.skip(
        "Tests de integración omitidos: Docker no disponible y DATABASE_URL no configurada.",
        allow_module_level=True,
    )


# ─── Fixture: URL de conexión (session-scoped, solo string) ──────────────────

@pytest.fixture(scope="session")
def pg_url() -> str:
    if _USA_DOCKER:
        from testcontainers.postgres import PostgresContainer
        pg = PostgresContainer(image="postgres:16-alpine", username="test", password="test", dbname="test_auth")
        pg.start()
        host = pg.get_container_host_ip()
        port = pg.get_exposed_port(5432)
        url = f"postgresql+asyncpg://test:test@{host}:{port}/test_auth"
        yield url
        pg.stop()
    else:
        yield _URL_BD_REAL


# ─── Migraciones (solo en Docker — Supabase ya está en head) ─────────────────

@pytest.fixture(scope="session", autouse=True)
def aplicar_migraciones(pg_url: str):
    """Aplica alembic upgrade head (solo cuando se usa contenedor Docker)."""
    if not _USA_DOCKER:
        return  # La BD real ya tiene las migraciones aplicadas

    import subprocess
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    alembic_bin = str(root / "venv" / "Scripts" / "alembic.exe")
    if not os.path.exists(alembic_bin):
        alembic_bin = "alembic"

    env = {
        **os.environ,
        "PYTHONPATH": str(root / "src"),
        "DATABASE_URL": pg_url,
        "JWT_SECRET_KEY": "test-secret-key-para-integracion-32chars!!",
        "APP_ENV": "development",
    }
    result = subprocess.run(
        [alembic_bin, "upgrade", "head"],
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"alembic upgrade head falló:\n{result.stdout}\n{result.stderr}")


# ─── Engine y sesión por test ─────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="session")
async def _engine(pg_url: str):
    """Motor SQLAlchemy async (session-scoped en el mismo event loop que los tests)."""
    eng = create_async_engine(
        pg_url,
        pool_size=5,
        max_overflow=0,
        echo=False,
        connect_args={"statement_cache_size": 0},
    )
    yield eng
    await eng.dispose()


@pytest.fixture(scope="session")
def session_factory(_engine):
    return async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session(session_factory):
    """
    Sesión de base de datos por test.
    Sin rollback explícito — cada test usa emails/IDs únicos (UUID), garantizando
    aislamiento sin necesidad de deshacer transacciones manualmente.
    """
    async with session_factory() as session:
        yield session
