"""Esquema completo del sistema auth — tablas, RLS, triggers y auditoría

revision : 001
revises  : (none)
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels = None
depends_on = None


def _sql(s: str) -> None:
    op.execute(sa.text(s))


def upgrade() -> None:

    # ── Enums ──────────────────────────────────────────────────────────────────
    _sql("DROP TYPE IF EXISTS estado_usuario_enum     CASCADE")
    _sql("DROP TYPE IF EXISTS tipo_actor_enum          CASCADE")
    _sql("DROP TYPE IF EXISTS resultado_auditoria_enum CASCADE")
    _sql("DROP TYPE IF EXISTS categoria_evento_enum    CASCADE")
    _sql("DROP TYPE IF EXISTS nivel_evento_enum        CASCADE")

    _sql("CREATE TYPE estado_usuario_enum     AS ENUM ('activo','inactivo','suspendido','pendiente_verificacion')")
    _sql("CREATE TYPE tipo_actor_enum          AS ENUM ('usuario','api_key','sistema','anonimo')")
    _sql("CREATE TYPE resultado_auditoria_enum AS ENUM ('exitoso','fallido','denegado')")
    _sql("CREATE TYPE categoria_evento_enum    AS ENUM ('auth','seguridad','usuario','rol','api_key','datos','sistema')")
    _sql("CREATE TYPE nivel_evento_enum        AS ENUM ('info','advertencia','critico','seguridad')")

    # ── Secuencia para auditoría ───────────────────────────────────────────────
    _sql("CREATE SEQUENCE IF NOT EXISTS auditoria_secuencia_seq")

    # ── Tabla: organizaciones ─────────────────────────────────────────────────
    _sql("""
        CREATE TABLE organizaciones (
            id             UUID        NOT NULL DEFAULT gen_random_uuid(),
            public_id      VARCHAR(40) NOT NULL,
            nombre         VARCHAR(200) NOT NULL,
            slug           VARCHAR(100) NOT NULL,
            activa         BOOLEAN     NOT NULL DEFAULT true,
            plan           VARCHAR(50) NOT NULL DEFAULT 'free',
            creado_en      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT pk_organizaciones           PRIMARY KEY (id),
            CONSTRAINT uq_organizaciones_public_id UNIQUE (public_id),
            CONSTRAINT uq_organizaciones_slug      UNIQUE (slug)
        )
    """)
    _sql("CREATE INDEX ix_organizaciones_public_id ON organizaciones (public_id)")
    _sql("CREATE INDEX ix_organizaciones_slug      ON organizaciones (slug)")
    _sql("CREATE INDEX ix_organizaciones_activa    ON organizaciones (activa)")

    # ── Tabla: usuarios ───────────────────────────────────────────────────────
    _sql("""
        CREATE TABLE usuarios (
            id               UUID                NOT NULL DEFAULT gen_random_uuid(),
            public_id        VARCHAR(35)         NOT NULL,
            email            VARCHAR(255)        NOT NULL,
            nombre           VARCHAR(100)        NOT NULL,
            apellido         VARCHAR(100)        NOT NULL,
            hash_password    VARCHAR(255)        NOT NULL,
            estado           estado_usuario_enum NOT NULL DEFAULT 'pendiente_verificacion',
            email_verificado BOOLEAN             NOT NULL DEFAULT false,
            ultimo_login     TIMESTAMPTZ,
            organization_id  UUID REFERENCES organizaciones (id) ON DELETE SET NULL,
            creado_en        TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
            actualizado_en   TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
            CONSTRAINT pk_usuarios        PRIMARY KEY (id),
            CONSTRAINT uq_usuarios_pub_id UNIQUE (public_id),
            CONSTRAINT uq_usuarios_email  UNIQUE (email)
        )
    """)
    _sql("CREATE INDEX ix_usuarios_email          ON usuarios (email)")
    _sql("CREATE INDEX ix_usuarios_public_id      ON usuarios (public_id)")
    _sql("CREATE INDEX ix_usuarios_estado         ON usuarios (estado)")
    _sql("CREATE INDEX ix_usuarios_creado_en      ON usuarios (creado_en DESC)")
    _sql("CREATE INDEX ix_usuarios_organization_id ON usuarios (organization_id)")
    _sql("CREATE INDEX ix_usuarios_org_estado     ON usuarios (organization_id, estado)")

    # ── Tabla: permisos ───────────────────────────────────────────────────────
    _sql("""
        CREATE TABLE permisos (
            id          UUID         NOT NULL DEFAULT gen_random_uuid(),
            recurso     VARCHAR(100) NOT NULL,
            accion      VARCHAR(100) NOT NULL,
            clave       VARCHAR(200) GENERATED ALWAYS AS (recurso || ':' || accion) STORED NOT NULL,
            descripcion VARCHAR(255) NOT NULL DEFAULT '',
            CONSTRAINT pk_permisos             PRIMARY KEY (id),
            CONSTRAINT uq_permisos_recurso_accion UNIQUE (recurso, accion),
            CONSTRAINT uq_permisos_clave       UNIQUE (clave)
        )
    """)

    # ── Tabla: roles ──────────────────────────────────────────────────────────
    _sql("""
        CREATE TABLE roles (
            id              UUID         NOT NULL DEFAULT gen_random_uuid(),
            public_id       VARCHAR(35)  NOT NULL,
            nombre          VARCHAR(100) NOT NULL,
            descripcion     VARCHAR(255) NOT NULL DEFAULT '',
            es_sistema      BOOLEAN      NOT NULL DEFAULT false,
            organization_id UUID REFERENCES organizaciones (id) ON DELETE CASCADE,
            creado_en       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            actualizado_en  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            CONSTRAINT pk_roles           PRIMARY KEY (id),
            CONSTRAINT uq_roles_public_id UNIQUE (public_id),
            CONSTRAINT uq_roles_nombre    UNIQUE (nombre)
        )
    """)
    _sql("CREATE INDEX ix_roles_public_id      ON roles (public_id)")
    _sql("CREATE INDEX ix_roles_nombre         ON roles (nombre)")
    _sql("CREATE INDEX ix_roles_organization_id ON roles (organization_id)")

    # ── Tabla: rol_permisos ───────────────────────────────────────────────────
    _sql("""
        CREATE TABLE rol_permisos (
            rol_id     UUID NOT NULL REFERENCES roles    (id) ON DELETE CASCADE,
            permiso_id UUID NOT NULL REFERENCES permisos (id) ON DELETE CASCADE,
            CONSTRAINT pk_rol_permisos PRIMARY KEY (rol_id, permiso_id)
        )
    """)

    # ── Tabla: usuario_roles ──────────────────────────────────────────────────
    _sql("""
        CREATE TABLE usuario_roles (
            id              UUID        NOT NULL DEFAULT gen_random_uuid(),
            usuario_id      UUID        NOT NULL REFERENCES usuarios (id) ON DELETE CASCADE,
            rol_id          UUID        NOT NULL REFERENCES roles    (id) ON DELETE CASCADE,
            asignado_por_id UUID,
            vigente_hasta   TIMESTAMPTZ,
            asignado_en     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT pk_usuario_roles              PRIMARY KEY (id),
            CONSTRAINT uq_usuario_roles_usuario_rol  UNIQUE (usuario_id, rol_id)
        )
    """)
    _sql("CREATE INDEX ix_usuario_roles_usuario_id ON usuario_roles (usuario_id)")

    # ── Tabla: api_keys ───────────────────────────────────────────────────────
    _sql("""
        CREATE TABLE api_keys (
            id              UUID         NOT NULL DEFAULT gen_random_uuid(),
            public_id       VARCHAR(35)  NOT NULL,
            nombre          VARCHAR(200) NOT NULL,
            key_prefix      VARCHAR(20)  NOT NULL,
            key_hash        VARCHAR(255) NOT NULL,
            propietario_id  UUID         NOT NULL REFERENCES usuarios (id) ON DELETE CASCADE,
            permisos        TEXT[]       NOT NULL DEFAULT '{}',
            activa          BOOLEAN      NOT NULL DEFAULT true,
            expira_en       TIMESTAMPTZ,
            ultimo_uso      TIMESTAMPTZ,
            organization_id UUID REFERENCES organizaciones (id) ON DELETE CASCADE,
            creado_en       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            CONSTRAINT pk_api_keys           PRIMARY KEY (id),
            CONSTRAINT uq_api_keys_public_id UNIQUE (public_id)
        )
    """)
    _sql("CREATE INDEX ix_api_keys_public_id      ON api_keys (public_id)")
    _sql("CREATE INDEX ix_api_keys_key_prefix     ON api_keys (key_prefix)")
    _sql("CREATE INDEX ix_api_keys_propietario_id ON api_keys (propietario_id)")
    _sql("CREATE INDEX ix_api_keys_organization_id ON api_keys (organization_id)")

    # ── Tabla: auditoria ──────────────────────────────────────────────────────
    _sql("""
        CREATE TABLE auditoria (
            id                UUID                    NOT NULL DEFAULT gen_random_uuid(),
            numero_secuencia  BIGINT                  NOT NULL DEFAULT nextval('auditoria_secuencia_seq'),
            timestamp         TIMESTAMPTZ             NOT NULL DEFAULT NOW(),
            timestamp_unix_ms BIGINT                  NOT NULL DEFAULT (EXTRACT(EPOCH FROM NOW())*1000)::BIGINT,
            correlation_id    VARCHAR(100)            NOT NULL DEFAULT '',

            actor_id          UUID,
            actor_email       VARCHAR(255),
            actor_ip          VARCHAR(45)             NOT NULL DEFAULT '',
            actor_user_agent  VARCHAR(500)            NOT NULL DEFAULT '',
            actor_tipo        tipo_actor_enum         NOT NULL,
            sesion_id         VARCHAR(100),
            api_key_id        UUID,

            categoria         categoria_evento_enum   NOT NULL DEFAULT 'sistema',
            nivel             nivel_evento_enum       NOT NULL DEFAULT 'info',
            accion            VARCHAR(200)            NOT NULL,
            resultado         resultado_auditoria_enum NOT NULL,
            resultado_detalle VARCHAR(1000),

            metodo_http       VARCHAR(10)             NOT NULL DEFAULT '',
            path              VARCHAR(500)            NOT NULL DEFAULT '',
            query_params      JSONB,
            codigo_respuesta  INTEGER,
            duracion_ms       INTEGER,

            recurso_tipo      VARCHAR(100)            NOT NULL DEFAULT '',
            recurso_id        VARCHAR(100),
            valor_anterior    JSONB,
            valor_nuevo       JSONB,
            diferencia        JSONB,

            metadatos         JSONB                   NOT NULL DEFAULT '{}',
            razon             VARCHAR(500),
            error_mensaje     VARCHAR(1000),

            organization_id   UUID REFERENCES organizaciones (id) ON DELETE SET NULL,

            hash_registro     VARCHAR(64)             NOT NULL DEFAULT '',
            firma_hmac        VARCHAR(100)            NOT NULL DEFAULT '',

            CONSTRAINT pk_auditoria PRIMARY KEY (id)
        )
    """)

    _sql("CREATE INDEX ix_aud_timestamp       ON auditoria (timestamp DESC)")
    _sql("CREATE INDEX ix_aud_secuencia        ON auditoria (numero_secuencia ASC)")
    _sql("CREATE INDEX ix_aud_actor_ts         ON auditoria (actor_id,        timestamp DESC)")
    _sql("CREATE INDEX ix_aud_actor_ip_ts      ON auditoria (actor_ip,        timestamp DESC)")
    _sql("CREATE INDEX ix_aud_sesion_ts        ON auditoria (sesion_id,       timestamp DESC) WHERE sesion_id IS NOT NULL")
    _sql("CREATE INDEX ix_aud_accion_ts        ON auditoria (accion,          timestamp DESC)")
    _sql("CREATE INDEX ix_aud_categoria_ts     ON auditoria (categoria,       timestamp DESC)")
    _sql("CREATE INDEX ix_aud_nivel_ts         ON auditoria (nivel,           timestamp DESC)")
    _sql("CREATE INDEX ix_aud_resultado_ts     ON auditoria (resultado,       timestamp DESC)")
    _sql("CREATE INDEX ix_aud_recurso          ON auditoria (recurso_tipo, recurso_id, timestamp DESC)")
    _sql("CREATE INDEX ix_aud_org_ts           ON auditoria (organization_id, timestamp DESC)")
    _sql("CREATE INDEX ix_aud_org_actor_ts     ON auditoria (organization_id, actor_id, timestamp DESC)")
    _sql("CREATE INDEX ix_aud_org_categoria    ON auditoria (organization_id, categoria, timestamp DESC)")

    # ── Función: actualizado_en automático ────────────────────────────────────
    _sql("""
        CREATE OR REPLACE FUNCTION fn_actualizar_actualizado_en()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN NEW.actualizado_en = NOW(); RETURN NEW; END; $$
    """)

    _sql("DROP TRIGGER IF EXISTS trg_usuarios_actualizado_en       ON usuarios")
    _sql("DROP TRIGGER IF EXISTS trg_organizaciones_actualizado_en ON organizaciones")
    _sql("DROP TRIGGER IF EXISTS trg_roles_actualizado_en          ON roles")

    _sql("""
        CREATE TRIGGER trg_usuarios_actualizado_en
            BEFORE UPDATE ON usuarios
            FOR EACH ROW EXECUTE FUNCTION fn_actualizar_actualizado_en()
    """)
    _sql("""
        CREATE TRIGGER trg_organizaciones_actualizado_en
            BEFORE UPDATE ON organizaciones
            FOR EACH ROW EXECUTE FUNCTION fn_actualizar_actualizado_en()
    """)
    _sql("""
        CREATE TRIGGER trg_roles_actualizado_en
            BEFORE UPDATE ON roles
            FOR EACH ROW EXECUTE FUNCTION fn_actualizar_actualizado_en()
    """)

    # ── RLS: funciones helper ─────────────────────────────────────────────────
    _sql("""
        CREATE OR REPLACE FUNCTION fn_tenant_id()
        RETURNS text LANGUAGE sql STABLE SECURITY INVOKER SET search_path = public AS $$
            SELECT COALESCE(current_setting('app.current_tenant', true), '')
        $$
    """)

    _sql("""
        CREATE OR REPLACE FUNCTION fn_user_id()
        RETURNS uuid LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path = public AS $$
        DECLARE v text;
        BEGIN
            v := current_setting('app.current_user_id', true);
            IF v IS NULL OR v = '' THEN RETURN NULL; END IF;
            RETURN v::uuid;
        EXCEPTION WHEN invalid_text_representation THEN RETURN NULL;
        END; $$
    """)

    # SECURITY DEFINER: bypassea RLS en usuario_roles/roles para evitar recursión
    _sql("""
        CREATE OR REPLACE FUNCTION fn_es_admin()
        RETURNS boolean LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public AS $$
        DECLARE v_uid uuid;
        BEGIN
            v_uid := fn_user_id();
            IF v_uid IS NULL THEN RETURN false; END IF;
            RETURN EXISTS (
                SELECT 1 FROM usuario_roles ur
                JOIN roles r ON r.id = ur.rol_id
                WHERE ur.usuario_id = v_uid
                  AND r.nombre = 'admin' AND r.es_sistema = true
                  AND (ur.vigente_hasta IS NULL OR ur.vigente_hasta > NOW())
            );
        END; $$
    """)

    # ── RLS: activar y definir policies ──────────────────────────────────────
    for tabla in ("usuarios", "roles", "api_keys", "auditoria", "organizaciones"):
        _sql(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")
        _sql(f"ALTER TABLE {tabla} FORCE  ROW LEVEL SECURITY")

    _sql("""
        CREATE POLICY rls_usuarios_tenant ON usuarios FOR ALL
        USING (fn_tenant_id()='' OR organization_id::text=fn_tenant_id())
        WITH CHECK (fn_tenant_id()='' OR organization_id::text=fn_tenant_id())
    """)
    _sql("""
        CREATE POLICY rls_roles_tenant ON roles FOR ALL
        USING (fn_tenant_id()='' OR organization_id IS NULL OR organization_id::text=fn_tenant_id())
        WITH CHECK (fn_tenant_id()='' OR organization_id IS NULL OR organization_id::text=fn_tenant_id())
    """)
    _sql("""
        CREATE POLICY rls_api_keys_tenant ON api_keys FOR ALL
        USING (fn_tenant_id()='' OR organization_id::text=fn_tenant_id())
        WITH CHECK (fn_tenant_id()='' OR organization_id::text=fn_tenant_id())
    """)
    _sql("""
        CREATE POLICY rls_auditoria_tenant ON auditoria FOR ALL
        USING (fn_tenant_id()='' OR organization_id IS NULL OR organization_id::text=fn_tenant_id())
        WITH CHECK (fn_tenant_id()='' OR organization_id IS NULL OR organization_id::text=fn_tenant_id())
    """)
    _sql("""
        CREATE POLICY rls_organizaciones_tenant ON organizaciones FOR ALL
        USING (fn_tenant_id()='' OR id::text=fn_tenant_id())
        WITH CHECK (fn_tenant_id()='' OR id::text=fn_tenant_id())
    """)

    for tabla in ("permisos", "rol_permisos", "usuario_roles"):
        _sql(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")
        _sql(f"ALTER TABLE {tabla} FORCE  ROW LEVEL SECURITY")

    _sql("CREATE POLICY rls_permisos_leer       ON permisos FOR SELECT USING (true)")
    _sql("CREATE POLICY rls_permisos_insertar   ON permisos FOR INSERT WITH CHECK (fn_tenant_id()='' OR fn_es_admin())")
    _sql("CREATE POLICY rls_permisos_actualizar ON permisos FOR UPDATE USING (fn_tenant_id()='' OR fn_es_admin()) WITH CHECK (fn_tenant_id()='' OR fn_es_admin())")
    _sql("CREATE POLICY rls_permisos_eliminar   ON permisos FOR DELETE USING (fn_tenant_id()='' OR fn_es_admin())")

    _sql("CREATE POLICY rls_rol_permisos_leer     ON rol_permisos FOR SELECT USING (true)")
    _sql("CREATE POLICY rls_rol_permisos_insertar ON rol_permisos FOR INSERT WITH CHECK (fn_tenant_id()='' OR fn_es_admin())")
    _sql("CREATE POLICY rls_rol_permisos_eliminar ON rol_permisos FOR DELETE USING (fn_tenant_id()='' OR fn_es_admin())")

    _sql("CREATE POLICY rls_usuario_roles_leer      ON usuario_roles FOR SELECT USING (fn_tenant_id()='' OR fn_es_admin() OR usuario_id=fn_user_id())")
    _sql("CREATE POLICY rls_usuario_roles_insertar  ON usuario_roles FOR INSERT WITH CHECK (fn_tenant_id()='' OR fn_es_admin())")
    _sql("CREATE POLICY rls_usuario_roles_actualizar ON usuario_roles FOR UPDATE USING (fn_tenant_id()='' OR fn_es_admin()) WITH CHECK (fn_tenant_id()='' OR fn_es_admin())")
    _sql("CREATE POLICY rls_usuario_roles_eliminar  ON usuario_roles FOR DELETE USING (fn_tenant_id()='' OR fn_es_admin())")

    # ── Trigger de auditoría a nivel de BD ────────────────────────────────────
    _sql("""
        CREATE OR REPLACE FUNCTION fn_auditoria_trigger()
        RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
        DECLARE
            v_ant  jsonb; v_new  jsonb;
            v_uid  uuid;  v_tid  uuid;
            v_rid  text;  v_ttxt text;
            v_sens CONSTANT text[] := ARRAY['hash_password','key_hash'];
            c text;
        BEGIN
            v_uid  := fn_user_id();
            v_ttxt := current_setting('app.current_tenant', true);
            IF v_ttxt IS NOT NULL AND v_ttxt <> '' THEN
                BEGIN v_tid := v_ttxt::uuid;
                EXCEPTION WHEN invalid_text_representation THEN v_tid := NULL; END;
            END IF;

            IF TG_OP IN ('UPDATE','DELETE') THEN
                v_ant := to_jsonb(OLD);
                FOREACH c IN ARRAY v_sens LOOP
                    IF v_ant ? c THEN v_ant := jsonb_set(v_ant, ARRAY[c], '"[REDACTED]"'); END IF;
                END LOOP;
            END IF;
            IF TG_OP IN ('INSERT','UPDATE') THEN
                v_new := to_jsonb(NEW);
                FOREACH c IN ARRAY v_sens LOOP
                    IF v_new ? c THEN v_new := jsonb_set(v_new, ARRAY[c], '"[REDACTED]"'); END IF;
                END LOOP;
            END IF;

            IF TG_OP = 'UPDATE' AND v_ant = v_new THEN RETURN NEW; END IF;

            v_rid := COALESCE((v_new->>'id'),(v_ant->>'id'),(v_new->>'rol_id'),(v_ant->>'rol_id'));

            IF v_tid IS NULL THEN
                BEGIN v_tid := COALESCE((v_new->>'organization_id')::uuid,(v_ant->>'organization_id')::uuid);
                EXCEPTION WHEN OTHERS THEN NULL; END;
            END IF;

            INSERT INTO auditoria (
                id, timestamp, timestamp_unix_ms,
                actor_id, actor_email, actor_ip, actor_user_agent, actor_tipo,
                categoria, nivel, accion, resultado,
                metodo_http, path, recurso_tipo, recurso_id,
                valor_anterior, valor_nuevo, organization_id,
                metadatos, hash_registro, firma_hmac
            ) VALUES (
                gen_random_uuid(), NOW(), (EXTRACT(EPOCH FROM NOW())*1000)::BIGINT,
                v_uid, NULL, '', '',
                CASE WHEN v_uid IS NOT NULL THEN 'usuario'::tipo_actor_enum ELSE 'sistema'::tipo_actor_enum END,
                'sistema'::categoria_evento_enum, 'info'::nivel_evento_enum,
                TG_TABLE_NAME||'.'||lower(TG_OP), 'exitoso'::resultado_auditoria_enum,
                '', '', TG_TABLE_NAME, v_rid,
                v_ant, v_new, v_tid,
                jsonb_build_object('fuente','trigger','operacion',TG_OP,'schema',TG_TABLE_SCHEMA),
                '', ''
            );
            RETURN COALESCE(NEW, OLD);
        EXCEPTION WHEN OTHERS THEN
            RAISE WARNING 'fn_auditoria_trigger: %.% op=% — %', TG_TABLE_SCHEMA, TG_TABLE_NAME, TG_OP, SQLERRM;
            RETURN COALESCE(NEW, OLD);
        END; $$
    """)

    for tabla, eventos in [
        ("usuarios",     "AFTER INSERT OR UPDATE OR DELETE"),
        ("roles",        "AFTER INSERT OR UPDATE OR DELETE"),
        ("api_keys",     "AFTER INSERT OR UPDATE OR DELETE"),
        ("usuario_roles","AFTER INSERT OR DELETE"),
        ("rol_permisos", "AFTER INSERT OR DELETE"),
    ]:
        _sql(f"DROP TRIGGER IF EXISTS trg_auditoria ON {tabla}")
        _sql(f"""
            CREATE TRIGGER trg_auditoria {eventos} ON {tabla}
            FOR EACH ROW EXECUTE FUNCTION fn_auditoria_trigger()
        """)

    # ── Datos semilla ─────────────────────────────────────────────────────────
    _sql("""
        INSERT INTO roles (id, public_id, nombre, descripcion, es_sistema) VALUES
            (gen_random_uuid(), 'rol_sistema_superadmin', 'superadmin', 'Acceso total — solo infraestructura', true),
            (gen_random_uuid(), 'rol_sistema_admin',      'admin',      'Administrador operativo',             true),
            (gen_random_uuid(), 'rol_sistema_usuario',    'usuario',    'Usuario estándar',                    true)
        ON CONFLICT (nombre) DO NOTHING
    """)

    _sql("""
        INSERT INTO permisos (id, recurso, accion, descripcion) VALUES
            (gen_random_uuid(), 'usuarios',  'crear',     'Crear nuevos usuarios'),
            (gen_random_uuid(), 'usuarios',  'leer',      'Consultar usuarios y perfiles'),
            (gen_random_uuid(), 'usuarios',  'editar',    'Modificar datos de usuarios'),
            (gen_random_uuid(), 'usuarios',  'eliminar',  'Eliminar usuarios del sistema'),
            (gen_random_uuid(), 'usuarios',  'suspender', 'Suspender o reactivar cuentas'),
            (gen_random_uuid(), 'roles',     'crear',     'Crear roles'),
            (gen_random_uuid(), 'roles',     'leer',      'Consultar roles y permisos'),
            (gen_random_uuid(), 'roles',     'editar',    'Modificar permisos de un rol'),
            (gen_random_uuid(), 'roles',     'eliminar',  'Eliminar roles no-sistema'),
            (gen_random_uuid(), 'roles',     'asignar',   'Asignar y revocar roles a usuarios'),
            (gen_random_uuid(), 'permisos',  'leer',      'Consultar el catálogo de permisos'),
            (gen_random_uuid(), 'permisos',  'editar',    'Gestionar el catálogo de permisos'),
            (gen_random_uuid(), 'api_keys',  'crear',     'Crear API Keys propias'),
            (gen_random_uuid(), 'api_keys',  'leer',      'Listar y consultar API Keys'),
            (gen_random_uuid(), 'api_keys',  'revocar',   'Revocar API Keys'),
            (gen_random_uuid(), 'auditoria', 'leer',      'Consultar el registro de auditoría'),
            (gen_random_uuid(), 'auditoria', 'exportar',  'Exportar registros completos a auditores externos'),
            (gen_random_uuid(), '*',         '*',         'Acceso total — bypass de cualquier verificación')
        ON CONFLICT (recurso, accion) DO NOTHING
    """)

    # superadmin → todos los permisos
    _sql("""
        INSERT INTO rol_permisos (rol_id, permiso_id)
        SELECT r.id, p.id FROM roles r, permisos p WHERE r.nombre = 'superadmin'
        ON CONFLICT DO NOTHING
    """)
    # admin → todos excepto el comodín
    _sql("""
        INSERT INTO rol_permisos (rol_id, permiso_id)
        SELECT r.id, p.id FROM roles r, permisos p
        WHERE r.nombre = 'admin' AND p.recurso != '*'
        ON CONFLICT DO NOTHING
    """)
    # usuario → autoservicio básico
    _sql("""
        INSERT INTO rol_permisos (rol_id, permiso_id)
        SELECT r.id, p.id FROM roles r, permisos p
        WHERE r.nombre = 'usuario'
          AND p.recurso IN ('api_keys','usuarios')
          AND p.accion  IN ('crear','leer','revocar','editar')
          AND NOT (p.recurso = 'usuarios' AND p.accion IN ('crear','eliminar','suspender'))
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    for tabla in ["rol_permisos","usuario_roles","api_keys","auditoria","roles","permisos","usuarios","organizaciones"]:
        _sql(f"DROP TRIGGER IF EXISTS trg_auditoria              ON {tabla}")
        _sql(f"DROP TRIGGER IF EXISTS trg_usuarios_actualizado_en ON {tabla}")
        _sql(f"DROP TRIGGER IF EXISTS trg_organizaciones_actualizado_en ON {tabla}")
        _sql(f"DROP TRIGGER IF EXISTS trg_roles_actualizado_en   ON {tabla}")

    _sql("DROP FUNCTION IF EXISTS fn_auditoria_trigger()")
    _sql("DROP FUNCTION IF EXISTS fn_es_admin()")
    _sql("DROP FUNCTION IF EXISTS fn_user_id()")
    _sql("DROP FUNCTION IF EXISTS fn_tenant_id()")
    _sql("DROP FUNCTION IF EXISTS fn_actualizar_actualizado_en()")

    for t in ["auditoria","api_keys","usuario_roles","rol_permisos","roles","permisos","usuarios","organizaciones"]:
        _sql(f"DROP TABLE IF EXISTS {t} CASCADE")

    _sql("DROP SEQUENCE IF EXISTS auditoria_secuencia_seq")
    _sql("DROP TYPE IF EXISTS nivel_evento_enum")
    _sql("DROP TYPE IF EXISTS categoria_evento_enum")
    _sql("DROP TYPE IF EXISTS resultado_auditoria_enum")
    _sql("DROP TYPE IF EXISTS tipo_actor_enum")
    _sql("DROP TYPE IF EXISTS estado_usuario_enum")
