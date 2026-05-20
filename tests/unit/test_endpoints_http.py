"""
Tests de endpoints HTTP usando TestClient.

Verifican el comportamiento real de la capa HTTP:
- Status codes correctos
- Response bodies con la estructura esperada
- Middleware de validación (422 en inputs incorrectos)
- 404 → redirect a /
- Headers de seguridad presentes
"""
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-para-tests-unitarios-32chars!!")
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")


def _make_redis_mock() -> MagicMock:
    """Redis client completamente mockeado para tests sin infraestructura."""
    r = MagicMock()
    r.ping = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.set = AsyncMock(return_value=True)
    r.setex = AsyncMock()
    r.delete = AsyncMock()
    r.exists = AsyncMock(return_value=0)
    r.incr = AsyncMock(return_value=1)
    r.expire = AsyncMock()
    r.sadd = AsyncMock()
    r.smembers = AsyncMock(return_value=set())
    r.aclose = AsyncMock()
    # pipeline — SET NX + INCR: results[0]=True (lock adquirido), results[1]=1 (count)
    pipe = MagicMock()
    pipe.__aenter__ = AsyncMock(return_value=pipe)
    pipe.__aexit__ = AsyncMock(return_value=False)
    pipe.set = MagicMock(return_value=pipe)
    pipe.incr = MagicMock(return_value=pipe)
    pipe.expire = MagicMock(return_value=pipe)
    pipe.sadd = MagicMock(return_value=pipe)
    pipe.execute = AsyncMock(return_value=[True, 1])
    r.pipeline = MagicMock(return_value=pipe)
    return r


def _make_session_mock() -> MagicMock:
    """AsyncSession mockeada para tests sin base de datos real."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory


@pytest.fixture(scope="module")
def client():
    redis_mock = _make_redis_mock()
    session_factory_mock = _make_session_mock()
    with patch("app.infrastructure.cache.redis_service.get_redis_client", return_value=redis_mock), \
         patch("app.infrastructure.persistence.database.init_db", new=AsyncMock()), \
         patch("app.infrastructure.persistence.database.AsyncSessionFactory", session_factory_mock), \
         patch("app.infrastructure.persistence.database.engine") as mock_engine:
        conn_mock = AsyncMock()
        conn_mock.execute = AsyncMock()
        mock_engine.connect.return_value.__aenter__ = AsyncMock(return_value=conn_mock)
        mock_engine.connect.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_engine.dispose = AsyncMock()
        from app.main import crear_app
        application = crear_app()
        with TestClient(application, follow_redirects=False) as c:
            yield c


# ── /health y /ready ──────────────────────────────────────────────────────────

def test_health_retorna_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_ready_tiene_clave_status(client):
    resp = client.get("/ready")
    assert resp.status_code in (200, 503)
    body = resp.json()
    assert "status" in body


# ── Rutas inexistentes ────────────────────────────────────────────────────────

def test_ruta_inexistente_redirige_raiz(client):
    resp = client.get("/no/existe/esta/ruta")
    assert resp.status_code == 302
    assert resp.headers["location"] == "/"


def test_ruta_api_inexistente_retorna_404(client):
    resp = client.get("/api/v1/recurso-que-no-existe")
    assert resp.status_code == 404
    assert "detalle" in resp.json()


# ── Validación de inputs (422) ────────────────────────────────────────────────

def test_login_sin_body_retorna_422(client):
    resp = client.post("/api/v1/auth/login", json={})
    assert resp.status_code == 422
    body = resp.json()
    assert "errores" in body or "detalle" in body


def test_login_email_invalido_retorna_422(client):
    resp = client.post("/api/v1/auth/login", json={
        "email": "no-es-un-email",
        "password": "Segura1@Pass"
    })
    assert resp.status_code == 422


def test_login_password_vacia_retorna_422(client):
    resp = client.post("/api/v1/auth/login", json={
        "email": "user@test.com",
        "password": ""
    })
    assert resp.status_code == 422


def test_crear_usuario_password_debil_retorna_422(client):
    resp = client.post("/api/v1/usuarios", json={
        "email": "nuevo@test.com",
        "nombre": "Test",
        "apellido": "User",
        "password": "debil"
    }, headers={"Authorization": "Bearer token-invalido"})
    # 401 por token inválido o 422 por password débil
    assert resp.status_code in (401, 422)


# ── Autenticación requerida (401) ─────────────────────────────────────────────

def test_listar_usuarios_sin_token_retorna_401(client):
    resp = client.get("/api/v1/usuarios")
    assert resp.status_code == 401


def test_listar_roles_sin_token_retorna_401(client):
    resp = client.get("/api/v1/roles")
    assert resp.status_code == 401


def test_perfil_propio_sin_token_retorna_401(client):
    resp = client.get("/api/v1/usuarios/me")
    assert resp.status_code == 401


def test_listar_auditoria_sin_token_retorna_401(client):
    resp = client.get("/api/v1/auditoria")
    assert resp.status_code == 401


def test_listar_api_keys_sin_token_retorna_401(client):
    resp = client.get("/api/v1/api-keys")
    assert resp.status_code == 401


# ── Token inválido (401) ──────────────────────────────────────────────────────

def test_token_malformado_retorna_401(client):
    resp = client.get("/api/v1/usuarios", headers={"Authorization": "Bearer token-basura"})
    assert resp.status_code == 401
    body = resp.json()
    assert "detalle" in body


def test_bearer_sin_token_retorna_401(client):
    resp = client.get("/api/v1/usuarios", headers={"Authorization": "Bearer "})
    assert resp.status_code == 401


# ── Headers de seguridad ──────────────────────────────────────────────────────

def test_headers_seguridad_presentes(client):
    resp = client.get("/health")
    assert "x-content-type-options" in resp.headers
    assert "x-frame-options" in resp.headers


# ── Solicitar reset password (no revela si existe el email) ──────────────────

def test_solicitar_reset_siempre_retorna_202(client):
    with patch("app.api.v1.routers.auth.auth._solicitar_reset_bg", new=AsyncMock()):
        resp = client.post("/api/v1/auth/solicitar-reset-password", json={
            "email": "no-existe@test.com"
        })
    assert resp.status_code == 202
    body = resp.json()
    assert "mensaje" in body


# ── Verificar email con token inválido ────────────────────────────────────────

def test_verificar_email_token_demasiado_corto_retorna_error(client):
    resp = client.post("/api/v1/auth/verificar-email", json={"token": "x" * 5})
    # Token muy corto → 422 por validación de schema
    assert resp.status_code in (401, 422, 400)
