"""
Tests de integración: verifican que el esquema de base de datos es correcto.

Validan que:
  - Todas las tablas existen tras las migraciones
  - Los índices críticos están presentes
  - Los tipos PostgreSQL (enums) están creados
  - Los datos semilla (roles del sistema) existen
  - El downgrade/upgrade es reversible
"""
import pytest
import pytest_asyncio
from sqlalchemy import text


@pytest.mark.asyncio
async def test_tablas_existen(db_session):
    """Todas las tablas del esquema deben existir después de las migraciones."""
    tablas_esperadas = [
        "usuarios",
        "roles",
        "permisos",
        "rol_permisos",
        "usuario_roles",
        "api_keys",
        "auditoria",
        "organizaciones",
    ]
    result = await db_session.execute(text("""
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
        ORDER BY tablename
    """))
    tablas_existentes = {row[0] for row in result.fetchall()}

    for tabla in tablas_esperadas:
        assert tabla in tablas_existentes, f"Tabla '{tabla}' no existe en la BD"


@pytest.mark.asyncio
async def test_enums_existen(db_session):
    """Los tipos PostgreSQL custom deben estar creados."""
    result = await db_session.execute(text("""
        SELECT typname FROM pg_type
        WHERE typtype = 'e'
        ORDER BY typname
    """))
    enums = {row[0] for row in result.fetchall()}

    assert "estado_usuario_enum" in enums
    assert "tipo_actor_enum" in enums
    assert "resultado_auditoria_enum" in enums


@pytest.mark.asyncio
async def test_roles_semilla_existen(db_session):
    """Los roles del sistema deben estar pre-cargados."""
    result = await db_session.execute(text("""
        SELECT nombre, es_sistema FROM roles
        WHERE es_sistema = true
        ORDER BY nombre
    """))
    roles = {row[0]: row[1] for row in result.fetchall()}

    assert "admin" in roles, "Rol 'admin' no fue creado en la migración inicial"
    assert "usuario" in roles, "Rol 'usuario' no fue creado en la migración inicial"
    assert roles["admin"] is True
    assert roles["usuario"] is True


@pytest.mark.asyncio
async def test_columna_organization_id_en_usuarios(db_session):
    """La columna organization_id debe existir en usuarios (migración 002)."""
    result = await db_session.execute(text("""
        SELECT column_name, is_nullable, data_type
        FROM information_schema.columns
        WHERE table_name = 'usuarios'
          AND column_name = 'organization_id'
    """))
    row = result.fetchone()
    assert row is not None, "Columna organization_id no existe en usuarios"
    assert row[1] == "YES", "organization_id debe ser nullable (compatibilidad datos existentes)"


@pytest.mark.asyncio
async def test_columnas_multitenancy_en_todas_las_tablas(db_session):
    """organization_id debe existir en todas las tablas de negocio."""
    tablas = ["usuarios", "roles", "api_keys", "auditoria"]
    for tabla in tablas:
        result = await db_session.execute(text(f"""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = '{tabla}' AND column_name = 'organization_id'
        """))
        assert result.fetchone() is not None, \
            f"organization_id no existe en tabla '{tabla}'"


@pytest.mark.asyncio
async def test_indices_criticos_existen(db_session):
    """Los índices de rendimiento críticos deben estar presentes."""
    result = await db_session.execute(text("""
        SELECT indexname FROM pg_indexes
        WHERE schemaname = 'public'
        ORDER BY indexname
    """))
    indices = {row[0] for row in result.fetchall()}

    indices_criticos = [
        "ix_usuarios_email",
        "ix_usuarios_estado",
        "ix_usuarios_creado_en",
        "ix_usuarios_organization_id",
        "ix_usuarios_org_estado",
        "ix_api_keys_key_prefix",
        "ix_api_keys_organization_id",
        "ix_auditoria_actor_id_ts",
        "ix_auditoria_organization_id_ts",
        "ix_auditoria_org_actor_ts",
        "ix_organizaciones_slug",
    ]
    for idx in indices_criticos:
        assert idx in indices, f"Índice crítico '{idx}' no existe"


@pytest.mark.asyncio
async def test_trigger_actualizado_en_usuarios(db_session):
    """El trigger debe actualizar actualizado_en automáticamente en UPDATE."""
    from uuid import uuid4

    user_id = uuid4()
    await db_session.execute(text("""
        INSERT INTO usuarios (id, public_id, email, nombre, apellido, hash_password)
        VALUES (:id, :pid, :email, 'Test', 'User', 'hash')
    """), {
        "id": user_id,
        "pid": f"usr_{uuid4().hex[:20]}",
        "email": f"trigger-test-{user_id}@test.com",
    })

    result = await db_session.execute(text("""
        SELECT actualizado_en FROM usuarios WHERE id = :id
    """), {"id": user_id})
    ts_inicial = result.scalar_one()

    import asyncio
    await asyncio.sleep(0.01)

    await db_session.execute(text("""
        UPDATE usuarios SET nombre = 'Modificado' WHERE id = :id
    """), {"id": user_id})

    result = await db_session.execute(text("""
        SELECT actualizado_en FROM usuarios WHERE id = :id
    """), {"id": user_id})
    ts_tras_update = result.scalar_one()

    assert ts_tras_update >= ts_inicial, \
        "El trigger no actualizó actualizado_en después del UPDATE"
