import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid6 import uuid7
from app.domain.entities.auth.usuario import Usuario, EstadoUsuario


@pytest.fixture
def usuario_activo() -> Usuario:
    u = Usuario(
        id=uuid7(),
        email="test@ejemplo.com",
        nombre="Juan",
        apellido="Pérez",
        estado=EstadoUsuario.ACTIVO,
        email_verificado=True,
    )
    u.cargar_permisos({"usuarios:leer", "usuarios:editar"})
    return u


@pytest.fixture
def mock_repo_usuario():
    repo = AsyncMock()
    repo.existe_email = AsyncMock(return_value=False)
    repo.guardar = AsyncMock()
    repo.actualizar = AsyncMock()
    repo.buscar_por_email = AsyncMock(return_value=None)
    repo.obtener_hash_password = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_repo_rol():
    repo = AsyncMock()
    repo.obtener_permisos_de_usuario = AsyncMock(return_value=set())
    repo.buscar_rol_por_nombre = AsyncMock(return_value=None)
    repo.asignar_rol_a_usuario = AsyncMock()
    return repo


@pytest.fixture
def mock_hash():
    h = AsyncMock()
    h.hashear = AsyncMock(return_value="$2b$12$hash_falso_para_tests")
    h.verificar = AsyncMock(return_value=True)
    return h


@pytest.fixture
def mock_cache():
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    cache.delete = AsyncMock()
    cache.exists = AsyncMock(return_value=False)
    cache.incr = AsyncMock(return_value=1)
    cache.smembers = AsyncMock(return_value=set())
    cache.set_nx = AsyncMock(return_value=True)
    cache.ttl = AsyncMock(return_value=900)
    return cache


@pytest.fixture
def mock_repo_api_key():
    repo = AsyncMock()
    repo.guardar = AsyncMock()
    repo.buscar_por_id = AsyncMock(return_value=None)
    repo.buscar_por_hash = AsyncMock(return_value=None)
    repo.listar_por_propietario = AsyncMock(return_value=[])
    repo.actualizar = AsyncMock()
    return repo
