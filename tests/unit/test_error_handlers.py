"""
Tests de error handlers y comportamiento de rutas no encontradas.
"""
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-para-tests-unitarios-32c")
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")


@pytest.fixture(scope="module")
def client():
    redis_mock = MagicMock()
    redis_mock.ping = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.set = AsyncMock(return_value=True)
    redis_mock.delete = AsyncMock()
    redis_mock.exists = AsyncMock(return_value=0)
    pipe = MagicMock()
    pipe.set = MagicMock(return_value=pipe)
    pipe.incr = MagicMock(return_value=pipe)
    pipe.execute = AsyncMock(return_value=[True, 1])
    redis_mock.pipeline = MagicMock(return_value=pipe)
    redis_mock.aclose = AsyncMock()

    session_mock = AsyncMock()
    session_mock.execute = AsyncMock()
    session_mock.commit = AsyncMock()
    session_mock.rollback = AsyncMock()
    session_mock.close = AsyncMock()
    session_factory = MagicMock()
    session_factory.return_value.__aenter__ = AsyncMock(return_value=session_mock)
    session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch("app.infrastructure.cache.redis_service.get_redis_client", return_value=redis_mock), \
         patch("app.infrastructure.persistence.database.init_db", new=AsyncMock()), \
         patch("app.infrastructure.persistence.database.AsyncSessionFactory", session_factory), \
         patch("app.infrastructure.persistence.database.engine") as mock_engine:
        mock_engine.dispose = AsyncMock()
        mock_engine.connect.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
        mock_engine.connect.return_value.__aexit__ = AsyncMock(return_value=False)
        from app.main import crear_app
        app = crear_app()
        with TestClient(app, follow_redirects=False) as c:
            yield c


def test_ruta_inexistente_redirige_a_raiz(client):
    """Cualquier ruta que no existe debe retornar 302 → /."""
    resp = client.get("/esta/ruta/no/existe")
    assert resp.status_code == 302
    assert resp.headers["location"] == "/"


def test_ruta_api_invalida_retorna_404(client):
    resp = client.get("/api/v1/ruta-que-no-existe")
    assert resp.status_code == 404
    assert "detalle" in resp.json()


def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
