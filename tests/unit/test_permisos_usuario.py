import pytest
from uuid6 import uuid7
from app.domain.entities.auth.usuario import Usuario, EstadoUsuario


def _usuario():
    return Usuario(id=uuid7(), email="x@x.com", nombre="X", apellido="Y")


def test_permiso_directo():
    u = _usuario()
    u.cargar_permisos({"usuarios:crear", "roles:leer"})
    assert u.tiene_permiso("usuarios:crear")
    assert u.tiene_permiso("roles:leer")
    assert not u.tiene_permiso("auditoria:leer")


def test_permiso_wildcard():
    u = _usuario()
    u.cargar_permisos({"*:*"})
    assert u.tiene_permiso("usuarios:crear")
    assert u.tiene_permiso("auditoria:eliminar")
    assert u.tiene_permiso("cualquier:cosa")


def test_sin_permisos():
    u = _usuario()
    assert not u.tiene_permiso("usuarios:leer")


def test_puede_autenticarse_activo():
    u = _usuario()
    u.estado = EstadoUsuario.ACTIVO
    assert u.puede_autenticarse()


def test_no_puede_autenticarse_suspendido():
    u = _usuario()
    u.estado = EstadoUsuario.SUSPENDIDO
    assert not u.puede_autenticarse()
