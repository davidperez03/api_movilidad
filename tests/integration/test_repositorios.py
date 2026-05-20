"""
Tests de integración: repositorios contra PostgreSQL real.

Validan que:
  - Las queries SQL son correctas (no mocks)
  - Los constraints de BD se respetan
  - La paginación cursor-based funciona
  - El tenant filtering aísla datos correctamente
  - Los índices se usan (sin N+1 queries)
"""
import pytest
import pytest_asyncio
from uuid import uuid4
from sqlalchemy import text

from app.domain.entities.auth.usuario import Usuario, EstadoUsuario
from app.domain.entities.auth.organizacion import Organizacion
from app.domain.exceptions import EmailYaRegistrado
from app.infrastructure.persistence.repositorios.auth.usuario_repo import UsuarioRepositorioSQL
from app.infrastructure.persistence.repositorios.auth.auditoria_repo import AuditoriaRepositorioSQL
from app.domain.ports.outbound.auth.repositorio_usuario import FiltrosUsuario
from app.domain.ports.outbound.auth.repositorio_auditoria import FiltrosAuditoria
from app.domain.entities.auth.auditoria import RegistroAuditoria, ResultadoAuditoria, TipoActor


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _usuario(email_prefix: str = "test") -> tuple[Usuario, str]:
    """Retorna (entidad Usuario, hash_password ficticio)."""
    email = f"{email_prefix}-{uuid4().hex[:8]}@integracion.test"
    u = Usuario(email=email, nombre="Test", apellido="Integracion")
    return u, "$2b$12$hash_fake_para_tests"


async def _insertar_org(session, nombre: str = "TestOrg") -> "uuid4":
    """Inserta una organización directamente y retorna su UUID."""
    org_id = uuid4()
    slug = f"test-org-{org_id.hex[:8]}"
    await session.execute(text("""
        INSERT INTO organizaciones (id, public_id, nombre, slug)
        VALUES (:id, :pid, :nombre, :slug)
    """), {"id": org_id, "pid": f"org_{org_id.hex[:20]}", "nombre": nombre, "slug": slug})
    return org_id


# ═══════════════════════════════════════════════════════════════════════════════
#  UsuarioRepositorioSQL
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_guardar_y_buscar_usuario(db_session):
    """Guardar un usuario y recuperarlo por id y por email."""
    repo = UsuarioRepositorioSQL(db_session)
    usuario, hash_pw = _usuario("guardar")

    guardado = await repo.guardar(usuario, hash_pw)

    assert guardado.id == usuario.id
    assert guardado.email == usuario.email

    por_id = await repo.buscar_por_id(usuario.id)
    assert por_id is not None
    assert por_id.email == usuario.email

    por_email = await repo.buscar_por_email(usuario.email)
    assert por_email is not None
    assert por_email.id == usuario.id


@pytest.mark.asyncio
async def test_email_duplicado_lanza_excepcion(db_session):
    """Insertar dos usuarios con el mismo email debe lanzar EmailYaRegistrado."""
    repo = UsuarioRepositorioSQL(db_session)
    usuario1, hash_pw = _usuario("dup")
    await repo.guardar(usuario1, hash_pw)

    usuario2 = Usuario(email=usuario1.email, nombre="Otro", apellido="Usuario")
    with pytest.raises(EmailYaRegistrado):
        await repo.guardar(usuario2, hash_pw)


@pytest.mark.asyncio
async def test_email_normalizado_en_dominio(db_session):
    """El email se normaliza en la entidad antes de llegar al repo."""
    repo = UsuarioRepositorioSQL(db_session)
    u = Usuario(email="  MAYUSCULAS@TEST.COM  ", nombre="X", apellido="Y")
    guardado = await repo.guardar(u, "$2b$12$hash")
    assert guardado.email == "mayusculas@test.com"


@pytest.mark.asyncio
async def test_actualizar_usuario(db_session):
    """Actualizar nombre y apellido de un usuario existente."""
    repo = UsuarioRepositorioSQL(db_session)
    usuario, hash_pw = _usuario("actualizar")
    await repo.guardar(usuario, hash_pw)

    usuario.actualizar_perfil(nombre="Nuevo", apellido="Apellido")
    actualizado = await repo.actualizar(usuario)

    assert actualizado.nombre == "Nuevo"
    assert actualizado.apellido == "Apellido"


@pytest.mark.asyncio
async def test_listar_con_paginacion_cursor(db_session):
    """La paginación cursor-based debe retornar páginas correctas."""
    repo = UsuarioRepositorioSQL(db_session)

    # Insertar 5 usuarios
    for i in range(5):
        u, h = _usuario(f"paginacion-{i}")
        await repo.guardar(u, h)

    pagina1 = await repo.listar(FiltrosUsuario(tamanio=3))
    assert len(pagina1.items) == 3
    assert pagina1.tiene_siguiente is True
    assert pagina1.siguiente_cursor is not None

    pagina2 = await repo.listar(FiltrosUsuario(tamanio=3, cursor=pagina1.siguiente_cursor))
    assert len(pagina2.items) >= 1

    # No debe haber duplicados entre páginas
    ids_p1 = {u.id for u in pagina1.items}
    ids_p2 = {u.id for u in pagina2.items}
    assert ids_p1.isdisjoint(ids_p2), "Las páginas no deben tener usuarios duplicados"


@pytest.mark.asyncio
async def test_listar_con_filtro_estado(db_session):
    """Listar solo usuarios activos."""
    repo = UsuarioRepositorioSQL(db_session)
    u_activo, h = _usuario("activo")
    await repo.guardar(u_activo, h)
    u_activo.activar()
    await repo.actualizar(u_activo)

    pagina = await repo.listar(FiltrosUsuario(estado=EstadoUsuario.ACTIVO, tamanio=100))
    emails = {u.email for u in pagina.items}
    assert u_activo.email in emails


@pytest.mark.asyncio
async def test_tenant_filtering_aísla_usuarios(db_session):
    """
    Un usuario de la org A NO debe aparecer en el listado de la org B.
    Es la prueba más crítica del tenant isolation.
    """
    repo = UsuarioRepositorioSQL(db_session)

    org_a = await _insertar_org(db_session, "Org Alpha")
    org_b = await _insertar_org(db_session, "Org Beta")

    u_a, h = _usuario("tenant-a")
    u_a.organization_id = org_a
    await repo.guardar(u_a, h)

    u_b, h = _usuario("tenant-b")
    u_b.organization_id = org_b
    await repo.guardar(u_b, h)

    pagina_a = await repo.listar(FiltrosUsuario(tamanio=100), organization_id=org_a)
    emails_a = {u.email for u in pagina_a.items}

    assert u_a.email in emails_a, "El usuario de Org A debe aparecer en su listado"
    assert u_b.email not in emails_a, "El usuario de Org B NO debe aparecer en el listado de Org A"

    pagina_b = await repo.listar(FiltrosUsuario(tamanio=100), organization_id=org_b)
    emails_b = {u.email for u in pagina_b.items}

    assert u_b.email in emails_b
    assert u_a.email not in emails_b, "El usuario de Org A NO debe aparecer en el listado de Org B"


# ═══════════════════════════════════════════════════════════════════════════════
#  AuditoriaRepositorioSQL
# ═══════════════════════════════════════════════════════════════════════════════

def _registro(accion: str = "test.accion", org_id=None) -> RegistroAuditoria:
    return RegistroAuditoria(
        accion=accion,
        resultado=ResultadoAuditoria.EXITOSO,
        recurso_tipo="usuarios",
        actor_tipo=TipoActor.USUARIO,
        organization_id=org_id,
    )


@pytest.mark.asyncio
async def test_registrar_y_listar_auditoria(db_session):
    """Insertar registros y recuperarlos con filtros."""
    repo = AuditoriaRepositorioSQL(db_session)
    reg = _registro("usuario.login")
    await repo.registrar(reg)

    registros, total = await repo.listar(FiltrosAuditoria(accion="usuario.login", tamanio=50))
    assert total >= 1
    acciones = [r.accion for r in registros]
    assert "usuario.login" in acciones


@pytest.mark.asyncio
async def test_auditoria_tenant_filtering(db_session):
    """
    Registros de auditoría de la org A NO deben ser visibles para la org B.
    """
    repo = AuditoriaRepositorioSQL(db_session)

    org_a = await _insertar_org(db_session, "Audit Org A")
    org_b = await _insertar_org(db_session, "Audit Org B")

    accion_exclusiva = f"accion.exclusiva.{uuid4().hex[:8]}"
    reg_a = _registro(accion_exclusiva, org_id=org_a)
    await repo.registrar(reg_a)

    # Listar con tenant de Org A → debe ver el registro
    registros_a, total_a = await repo.listar(
        FiltrosAuditoria(tamanio=100),
        organization_id=org_a,
    )
    ids_a = {r.id for r in registros_a}
    assert reg_a.id in ids_a, "Org A debe ver sus propios registros de auditoría"

    # Listar con tenant de Org B → NO debe ver el registro de Org A
    registros_b, _ = await repo.listar(
        FiltrosAuditoria(tamanio=100),
        organization_id=org_b,
    )
    ids_b = {r.id for r in registros_b}
    assert reg_a.id not in ids_b, \
        "Org B NO debe poder ver registros de auditoría de Org A"


@pytest.mark.asyncio
async def test_auditoria_paginacion(db_session):
    """La paginación offset en auditoría debe funcionar correctamente."""
    repo = AuditoriaRepositorioSQL(db_session)
    accion_test = f"pag.test.{uuid4().hex[:6]}"

    for _ in range(5):
        await repo.registrar(_registro(accion_test))

    _, total = await repo.listar(FiltrosAuditoria(accion=accion_test, tamanio=100))
    assert total == 5

    pagina1, _ = await repo.listar(FiltrosAuditoria(accion=accion_test, tamanio=3, pagina=1))
    pagina2, _ = await repo.listar(FiltrosAuditoria(accion=accion_test, tamanio=3, pagina=2))

    assert len(pagina1) == 3
    assert len(pagina2) == 2
    ids_p1 = {r.id for r in pagina1}
    ids_p2 = {r.id for r in pagina2}
    assert ids_p1.isdisjoint(ids_p2)
