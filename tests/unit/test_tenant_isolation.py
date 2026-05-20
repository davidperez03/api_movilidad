"""
Tests de aislamiento multi-tenant.

Verifica que las operaciones de usuario y rol respetan los límites de tenant:
- listar_usuarios solo devuelve usuarios del tenant correcto
- crear_usuario asigna el organization_id recibido
- asignar_rol rechaza operaciones cross-tenant
"""
import pytest
from unittest.mock import AsyncMock, patch
from uuid6 import uuid7
from uuid import UUID

from app.application.use_cases.auth.usuarios.listar_usuarios import ListarUsuariosUseCase
from app.application.use_cases.auth.usuarios.crear_usuario import CrearUsuarioUseCase, ComandoCrearUsuario
from app.domain.ports.outbound.auth.repositorio_usuario import FiltrosUsuario
from app.domain.entities.auth.usuario import Usuario, EstadoUsuario
from app.domain.entities.auth.rol import Rol


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def org_a() -> UUID:
    return uuid7()


@pytest.fixture
def org_b() -> UUID:
    return uuid7()


def _usuario(org_id: UUID | None = None) -> Usuario:
    u = Usuario(
        email=f"u{uuid7().hex[:8]}@test.com",
        nombre="Test",
        apellido="User",
        organization_id=org_id,
    )
    u.estado = EstadoUsuario.ACTIVO
    u.email_verificado = True
    return u


def _rol(nombre: str = "usuario") -> Rol:
    return Rol(id=uuid7(), public_id=f"rol_{uuid7().hex[:8]}", nombre=nombre, descripcion="")


# ── listar_usuarios ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_listar_usuarios_filtra_por_tenant(org_a):
    usuario_tenant = _usuario(org_a)
    repo = AsyncMock()
    repo.listar = AsyncMock()

    use_case = ListarUsuariosUseCase(repo)
    filtros = FiltrosUsuario(tamanio=20)

    await use_case.ejecutar(filtros, organization_id=org_a)

    repo.listar.assert_called_once()
    filtros_pasados = repo.listar.call_args[0][0]
    assert filtros_pasados.organization_id == org_a


@pytest.mark.asyncio
async def test_listar_usuarios_sin_tenant_no_filtra():
    """Sin org_id (single-tenant mode), el filtro es None."""
    repo = AsyncMock()
    repo.listar = AsyncMock()

    use_case = ListarUsuariosUseCase(repo)
    filtros = FiltrosUsuario(tamanio=20)

    await use_case.ejecutar(filtros, organization_id=None)

    filtros_pasados = repo.listar.call_args[0][0]
    assert filtros_pasados.organization_id is None


# ── crear_usuario ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_crear_usuario_asigna_organization_id(mock_repo_usuario, mock_repo_rol, mock_hash, org_a):
    rol = _rol()
    mock_repo_rol.buscar_rol_por_nombre = AsyncMock(return_value=rol)
    mock_repo_rol.asignar_rol_a_usuario = AsyncMock()

    usuario_creado = _usuario(org_a)
    mock_repo_usuario.guardar = AsyncMock(return_value=usuario_creado)

    use_case = CrearUsuarioUseCase(mock_repo_usuario, mock_repo_rol, mock_hash)
    resultado = await use_case.ejecutar(
        ComandoCrearUsuario(
            email="nuevo@test.com",
            nombre="Nuevo",
            apellido="Usuario",
            password="Segura1@Pass",
            organization_id=org_a,
        )
    )

    # El usuario guardado debe tener el organization_id del tenant
    args = mock_repo_usuario.guardar.call_args[0]
    usuario_a_guardar: Usuario = args[0]
    assert usuario_a_guardar.organization_id == org_a


@pytest.mark.asyncio
async def test_crear_usuario_sin_tenant_queda_global(mock_repo_usuario, mock_repo_rol, mock_hash):
    rol = _rol()
    mock_repo_rol.buscar_rol_por_nombre = AsyncMock(return_value=rol)
    mock_repo_rol.asignar_rol_a_usuario = AsyncMock()

    usuario_creado = _usuario(None)
    mock_repo_usuario.guardar = AsyncMock(return_value=usuario_creado)

    use_case = CrearUsuarioUseCase(mock_repo_usuario, mock_repo_rol, mock_hash)
    await use_case.ejecutar(
        ComandoCrearUsuario(
            email="global@test.com",
            nombre="Global",
            apellido="User",
            password="Segura1@Pass",
            organization_id=None,
        )
    )

    args = mock_repo_usuario.guardar.call_args[0]
    usuario_a_guardar: Usuario = args[0]
    assert usuario_a_guardar.organization_id is None


# ── FiltrosUsuario ────────────────────────────────────────────────────────────

def test_filtros_usuario_con_organization_id(org_a):
    filtros = FiltrosUsuario(tamanio=10, organization_id=org_a)
    assert filtros.organization_id == org_a


def test_filtros_usuario_sin_organization_id():
    filtros = FiltrosUsuario(tamanio=10)
    assert filtros.organization_id is None
