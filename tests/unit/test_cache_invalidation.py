"""
Tests de invalidación de caché de permisos.

Verifica que asignar o revocar un rol elimina inmediatamente
las entradas de caché en Redis para ese usuario.
"""
import pytest
from unittest.mock import AsyncMock, patch, call
from uuid6 import uuid7

from app.application.use_cases.auth.roles.asignar_rol_a_usuario import (
    AsignarRolAUsuarioUseCase, ComandoAsignarRolAUsuario,
)
from app.application.use_cases.auth.roles.revocar_rol_de_usuario import (
    RevocarRolDeUsuarioUseCase, ComandoRevocarRol,
)
from app.domain.entities.auth.usuario import Usuario, EstadoUsuario
from app.domain.entities.auth.rol import Rol, AsignacionRol


# ── Helpers ───────────────────────────────────────────────────────────────────

def _usuario_activo() -> Usuario:
    u = Usuario(
        email=f"u{uuid7().hex[:6]}@test.com",
        nombre="Cache",
        apellido="Test",
        estado=EstadoUsuario.ACTIVO,
        email_verificado=True,
    )
    return u


def _rol() -> Rol:
    return Rol(id=uuid7(), public_id=f"rol_{uuid7().hex[:8]}", nombre="admin", descripcion="")


# ── asignar_rol_a_usuario ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_asignar_rol_invalida_cache_permisos():
    usuario = _usuario_activo()
    rol = _rol()

    repo_rol = AsyncMock()
    repo_rol.asignar_rol_a_usuario = AsyncMock(
        return_value=AsignacionRol(usuario_id=usuario.id, rol_id=rol.id)
    )

    repo_usuario = AsyncMock()
    repo_usuario.buscar_por_id = AsyncMock(return_value=usuario)

    cache = AsyncMock()
    cache.delete = AsyncMock()

    use_case = AsignarRolAUsuarioUseCase(repo_rol, repo_usuario, cache)
    await use_case.ejecutar(
        ComandoAsignarRolAUsuario(
            usuario_id=usuario.id,
            rol_id=rol.id,
            asignado_por_id=uuid7(),
        )
    )

    # El use case debe limpiar el cache de permisos de ese usuario
    claves_eliminadas = [c.args[0] for c in cache.delete.call_args_list]
    assert any(f"permisos_usuario:{usuario.id}" in c for c in claves_eliminadas), (
        "Se debe invalidar la clave permisos_usuario:{id} tras asignar rol"
    )


# ── revocar_rol_de_usuario ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_revocar_rol_invalida_cache_permisos():
    usuario = _usuario_activo()
    rol = _rol()

    repo_rol = AsyncMock()
    repo_rol.revocar_rol_de_usuario = AsyncMock()

    cache = AsyncMock()
    cache.delete = AsyncMock()

    use_case = RevocarRolDeUsuarioUseCase(repo_rol, cache)
    await use_case.ejecutar(
        ComandoRevocarRol(usuario_id=usuario.id, rol_id=rol.id)
    )

    claves_eliminadas = [c.args[0] for c in cache.delete.call_args_list]
    assert any(f"permisos_usuario:{usuario.id}" in c for c in claves_eliminadas), (
        "Se debe invalidar la clave permisos_usuario:{id} tras revocar rol"
    )
