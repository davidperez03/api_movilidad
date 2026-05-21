"""Módulos movilidad, parqueadero y NUNC

revision : 002
revises  : 001
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels = None
depends_on = None


def _sql(s: str) -> None:
    op.execute(sa.text(s))


def upgrade() -> None:

    # ── Enums ──────────────────────────────────────────────────────────────────
    _sql("""
        DO $$ BEGIN
            CREATE TYPE tipo_servicio_enum AS ENUM ('particular', 'publico', 'otro');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$
    """)
    _sql("""
        DO $$ BEGIN
            CREATE TYPE estado_traslado_enum AS ENUM ('sin_asignar', 'revisado', 'con_novedades', 'aprobado', 'enviado_organismo', 'trasladado');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$
    """)
    _sql("""
        DO $$ BEGIN
            CREATE TYPE estado_radicacion_enum AS ENUM ('sin_asignar', 'pendiente_radicar', 'con_novedades', 'enviado_devolucion', 'recibido', 'revisado', 'radicado');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$
    """)
    _sql("""
        DO $$ BEGIN
            CREATE TYPE tipo_novedad_enum AS ENUM ('documentos_faltantes', 'documentos_incorrectos', 'placa_incorrecta', 'otro');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$
    """)
    _sql("""
        DO $$ BEGIN
            CREATE TYPE prioridad_novedad_enum AS ENUM ('baja', 'media', 'alta', 'critica');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$
    """)
    _sql("""
        DO $$ BEGIN
            CREATE TYPE estado_novedad_enum AS ENUM ('pendiente', 'en_revision', 'resuelta');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$
    """)
    _sql("""
        DO $$ BEGIN
            CREATE TYPE tipo_festivo_enum AS ENUM ('religioso', 'civil', 'puente');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$
    """)
    _sql("""
        DO $$ BEGIN
            CREATE TYPE turno_inspeccion_enum AS ENUM ('dia', 'noche');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$
    """)
    _sql("""
        DO $$ BEGIN
            CREATE TYPE estado_item_enum AS ENUM ('bueno', 'regular', 'malo', 'no_aplica');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$
    """)
    _sql("""
        DO $$ BEGIN
            CREATE TYPE tipo_vehiculo_parqueadero_enum AS ENUM ('grua_plataforma', 'camioneta', 'furgon', 'otro');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$
    """)
    _sql("""
        DO $$ BEGIN
            CREATE TYPE estado_sesion_nunc_enum AS ENUM ('activa', 'cerrada', 'expirada');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$
    """)

    # ── Tablas Movilidad ───────────────────────────────────────────────────────
    _sql("""
        CREATE TABLE mov_festivos_colombia (
            fecha  DATE         PRIMARY KEY,
            nombre VARCHAR(200) NOT NULL,
            tipo   tipo_festivo_enum NOT NULL
        )
    """)

    _sql("""
        CREATE TABLE mov_organismos_transito (
            id             UUID         NOT NULL DEFAULT gen_random_uuid(),
            public_id      VARCHAR(40)  UNIQUE NOT NULL,
            nombre         VARCHAR(300) NOT NULL,
            tipo           VARCHAR(100) NOT NULL DEFAULT '',
            municipio      VARCHAR(200) NOT NULL DEFAULT '',
            departamento   VARCHAR(200) NOT NULL DEFAULT '',
            telefono       VARCHAR(50),
            direccion      VARCHAR(500),
            activo         BOOLEAN      NOT NULL DEFAULT true,
            search_vector  TSVECTOR,
            creado_en      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            actualizado_en TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            CONSTRAINT pk_mov_organismos_transito PRIMARY KEY (id)
        )
    """)

    _sql("""
        CREATE TABLE mov_empresas_transporte (
            id             UUID         NOT NULL DEFAULT gen_random_uuid(),
            public_id      VARCHAR(40)  UNIQUE NOT NULL,
            nombre         VARCHAR(300) NOT NULL,
            activo         BOOLEAN      NOT NULL DEFAULT true,
            creado_en      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            actualizado_en TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            CONSTRAINT pk_mov_empresas_transporte PRIMARY KEY (id)
        )
    """)

    _sql("""
        CREATE TABLE mov_cuentas_vehiculos (
            id              UUID         NOT NULL DEFAULT gen_random_uuid(),
            public_id       VARCHAR(40)  UNIQUE NOT NULL,
            placa           VARCHAR(10)  UNIQUE NOT NULL,
            numero_cuenta   VARCHAR(20)  UNIQUE NOT NULL DEFAULT '',
            tipo_servicio   tipo_servicio_enum NOT NULL,
            creado_por      UUID REFERENCES usuarios(id) ON DELETE SET NULL,
            organization_id UUID REFERENCES organizaciones(id) ON DELETE SET NULL,
            creado_en       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            actualizado_en  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            version         INTEGER      NOT NULL DEFAULT 1,
            CONSTRAINT pk_mov_cuentas_vehiculos PRIMARY KEY (id)
        )
    """)

    _sql("""
        CREATE TABLE mov_traslados (
            id                        UUID         NOT NULL DEFAULT gen_random_uuid(),
            public_id                 VARCHAR(40)  UNIQUE NOT NULL,
            cuenta_id                 UUID         NOT NULL REFERENCES mov_cuentas_vehiculos(id) ON DELETE CASCADE,
            organismo_destino_id      UUID REFERENCES mov_organismos_transito(id) ON DELETE SET NULL,
            estado                    estado_traslado_enum NOT NULL DEFAULT 'sin_asignar',
            numero_guia               VARCHAR(100),
            empresa_transportadora_id UUID REFERENCES mov_empresas_transporte(id) ON DELETE SET NULL,
            aprobado_en               TIMESTAMPTZ,
            vencimiento               DATE,
            completado_en             TIMESTAMPTZ,
            observaciones             TEXT,
            creado_por                UUID REFERENCES usuarios(id) ON DELETE SET NULL,
            actualizado_por           UUID REFERENCES usuarios(id) ON DELETE SET NULL,
            organization_id           UUID REFERENCES organizaciones(id) ON DELETE SET NULL,
            creado_en                 TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            actualizado_en            TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            version                   INTEGER      NOT NULL DEFAULT 1,
            CONSTRAINT pk_mov_traslados PRIMARY KEY (id)
        )
    """)

    _sql("""
        CREATE TABLE mov_radicaciones (
            id                        UUID         NOT NULL DEFAULT gen_random_uuid(),
            public_id                 VARCHAR(40)  UNIQUE NOT NULL,
            cuenta_id                 UUID         NOT NULL REFERENCES mov_cuentas_vehiculos(id) ON DELETE CASCADE,
            organismo_origen_id       UUID REFERENCES mov_organismos_transito(id) ON DELETE SET NULL,
            estado                    estado_radicacion_enum NOT NULL DEFAULT 'sin_asignar',
            numero_guia               VARCHAR(100),
            empresa_transportadora_id UUID REFERENCES mov_empresas_transporte(id) ON DELETE SET NULL,
            numero_guia_devolucion    VARCHAR(100),
            radicado_en               TIMESTAMPTZ,
            vencimiento               DATE,
            completado_en             TIMESTAMPTZ,
            observaciones             TEXT,
            creado_por                UUID REFERENCES usuarios(id) ON DELETE SET NULL,
            actualizado_por           UUID REFERENCES usuarios(id) ON DELETE SET NULL,
            organization_id           UUID REFERENCES organizaciones(id) ON DELETE SET NULL,
            creado_en                 TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            actualizado_en            TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            version                   INTEGER      NOT NULL DEFAULT 1,
            CONSTRAINT pk_mov_radicaciones PRIMARY KEY (id)
        )
    """)

    _sql("""
        CREATE TABLE mov_notificaciones_radicacion (
            id                     UUID    NOT NULL DEFAULT gen_random_uuid(),
            radicacion_id          UUID    UNIQUE NOT NULL REFERENCES mov_radicaciones(id) ON DELETE CASCADE,
            solicitante_notificado BOOLEAN NOT NULL DEFAULT false,
            notificado_en          TIMESTAMPTZ,
            observaciones          TEXT,
            creado_por             UUID REFERENCES usuarios(id) ON DELETE SET NULL,
            actualizado_por        UUID REFERENCES usuarios(id) ON DELETE SET NULL,
            creado_en              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            actualizado_en         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT pk_mov_notificaciones_radicacion PRIMARY KEY (id)
        )
    """)

    _sql("""
        CREATE TABLE mov_novedades (
            id              UUID         NOT NULL DEFAULT gen_random_uuid(),
            public_id       VARCHAR(40)  UNIQUE NOT NULL,
            proceso_tipo    VARCHAR(20)  NOT NULL,
            proceso_id      UUID         NOT NULL,
            tipo_novedad    tipo_novedad_enum NOT NULL,
            prioridad       prioridad_novedad_enum NOT NULL DEFAULT 'media',
            descripcion     TEXT         NOT NULL,
            estado          estado_novedad_enum NOT NULL DEFAULT 'pendiente',
            solucion        TEXT,
            resuelto_por    UUID REFERENCES usuarios(id) ON DELETE SET NULL,
            resuelto_en     TIMESTAMPTZ,
            creado_por      UUID REFERENCES usuarios(id) ON DELETE SET NULL,
            organization_id UUID REFERENCES organizaciones(id) ON DELETE SET NULL,
            creado_en       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            actualizado_en  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            CONSTRAINT pk_mov_novedades PRIMARY KEY (id)
        )
    """)

    _sql("""
        CREATE TABLE mov_adjuntos_novedades (
            id             UUID         NOT NULL DEFAULT gen_random_uuid(),
            novedad_id     UUID         NOT NULL REFERENCES mov_novedades(id) ON DELETE CASCADE,
            nombre_archivo VARCHAR(500) NOT NULL,
            url            TEXT         NOT NULL,
            tamano         INTEGER,
            mime_type      VARCHAR(100),
            cargado_por    UUID REFERENCES usuarios(id) ON DELETE SET NULL,
            cargado_en     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            CONSTRAINT pk_mov_adjuntos_novedades PRIMARY KEY (id)
        )
    """)

    _sql("""
        CREATE TABLE mov_historial_acciones (
            id              UUID         NOT NULL DEFAULT gen_random_uuid(),
            cuenta_id       UUID REFERENCES mov_cuentas_vehiculos(id) ON DELETE CASCADE,
            proceso_tipo    VARCHAR(20),
            proceso_id      UUID,
            tipo_accion     VARCHAR(50)  NOT NULL,
            estado_anterior VARCHAR(50),
            estado_nuevo    VARCHAR(50),
            realizado_por   UUID REFERENCES usuarios(id) ON DELETE SET NULL,
            organization_id UUID REFERENCES organizaciones(id) ON DELETE SET NULL,
            ip_address      VARCHAR(45),
            user_agent      VARCHAR(500),
            detalles        JSONB        NOT NULL DEFAULT '{}',
            hash_anterior   VARCHAR(64)  NOT NULL DEFAULT '',
            hash_registro   VARCHAR(64)  NOT NULL DEFAULT '',
            creado_en       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            CONSTRAINT pk_mov_historial_acciones PRIMARY KEY (id)
        )
    """)

    # ── Tablas Parqueadero ─────────────────────────────────────────────────────
    _sql("""
        CREATE TABLE parq_vehiculos (
            id                        UUID         NOT NULL DEFAULT gen_random_uuid(),
            public_id                 VARCHAR(40)  UNIQUE NOT NULL,
            placa                     VARCHAR(10)  UNIQUE NOT NULL,
            marca                     VARCHAR(100) NOT NULL DEFAULT '',
            modelo                    VARCHAR(100) NOT NULL DEFAULT '',
            tipo_vehiculo             tipo_vehiculo_parqueadero_enum NOT NULL,
            soat_aseguradora          VARCHAR(200),
            soat_vencimiento          DATE,
            tecnomecanica_vencimiento DATE,
            activo                    BOOLEAN      NOT NULL DEFAULT true,
            creado_por                UUID REFERENCES usuarios(id) ON DELETE SET NULL,
            organization_id           UUID REFERENCES organizaciones(id) ON DELETE SET NULL,
            creado_en                 TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            actualizado_en            TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            version                   INTEGER      NOT NULL DEFAULT 1,
            CONSTRAINT pk_parq_vehiculos PRIMARY KEY (id)
        )
    """)

    _sql("""
        CREATE TABLE parq_datos_personal (
            id                           UUID        NOT NULL DEFAULT gen_random_uuid(),
            perfil_id                    UUID        UNIQUE NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            licencia_numero              VARCHAR(50),
            licencia_categoria           VARCHAR(5),
            licencia_vencimiento         DATE,
            documento_tipo               VARCHAR(5),
            documento_numero             VARCHAR(50),
            telefono                     VARCHAR(20),
            contacto_emergencia_nombre   VARCHAR(200),
            contacto_emergencia_telefono VARCHAR(20),
            notas                        TEXT,
            organization_id              UUID REFERENCES organizaciones(id) ON DELETE SET NULL,
            creado_en                    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            actualizado_en               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT pk_parq_datos_personal PRIMARY KEY (id)
        )
    """)

    _sql("""
        CREATE TABLE parq_items_catalogo (
            id              UUID         NOT NULL DEFAULT gen_random_uuid(),
            public_id       VARCHAR(40)  UNIQUE NOT NULL,
            codigo          VARCHAR(50)  UNIQUE NOT NULL,
            nombre          VARCHAR(200) NOT NULL,
            categoria       VARCHAR(50)  NOT NULL,
            descripcion     TEXT,
            orden           INTEGER      NOT NULL DEFAULT 0,
            activo          BOOLEAN      NOT NULL DEFAULT true,
            organization_id UUID REFERENCES organizaciones(id) ON DELETE SET NULL,
            creado_en       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            actualizado_en  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            CONSTRAINT pk_parq_items_catalogo PRIMARY KEY (id)
        )
    """)

    _sql("""
        CREATE TABLE parq_inspecciones (
            id                             UUID        NOT NULL DEFAULT gen_random_uuid(),
            public_id                      VARCHAR(40) UNIQUE NOT NULL,
            codigo                         VARCHAR(20) UNIQUE NOT NULL,
            vehiculo_id                    UUID        NOT NULL REFERENCES parq_vehiculos(id) ON DELETE RESTRICT,
            operador_id                    UUID        NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
            auxiliar_id                    UUID REFERENCES usuarios(id) ON DELETE SET NULL,
            inspector_id                   UUID        NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
            fecha                          DATE        NOT NULL,
            hora                           TIME        NOT NULL,
            turno                          turno_inspeccion_enum NOT NULL,
            es_apto                        BOOLEAN     NOT NULL DEFAULT false,
            observaciones                  TEXT,
            firma_operador                 TEXT,
            firma_inspector                TEXT,
            fotos                          JSONB       NOT NULL DEFAULT '[]',
            soat_vencimiento_snap          DATE,
            tecnomecanica_vencimiento_snap DATE,
            licencia_vencimiento_snap      DATE,
            creado_por                     UUID REFERENCES usuarios(id) ON DELETE SET NULL,
            actualizado_por                UUID REFERENCES usuarios(id) ON DELETE SET NULL,
            organization_id                UUID REFERENCES organizaciones(id) ON DELETE SET NULL,
            creado_en                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            actualizado_en                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            version                        INTEGER     NOT NULL DEFAULT 1,
            CONSTRAINT pk_parq_inspecciones PRIMARY KEY (id)
        )
    """)

    _sql("""
        CREATE TABLE parq_items_inspeccion (
            id               UUID         NOT NULL DEFAULT gen_random_uuid(),
            inspeccion_id    UUID         NOT NULL REFERENCES parq_inspecciones(id) ON DELETE CASCADE,
            item_catalogo_id UUID         NOT NULL REFERENCES parq_items_catalogo(id) ON DELETE RESTRICT,
            codigo           VARCHAR(50)  NOT NULL,
            nombre           VARCHAR(200) NOT NULL,
            categoria        VARCHAR(50)  NOT NULL,
            estado           estado_item_enum NOT NULL,
            observaciones    TEXT,
            fotos            JSONB        NOT NULL DEFAULT '[]',
            subsanado        BOOLEAN      NOT NULL DEFAULT false,
            subsanado_por    UUID REFERENCES usuarios(id) ON DELETE SET NULL,
            subsanado_en     TIMESTAMPTZ,
            foto_subsanacion JSONB        NOT NULL DEFAULT '[]',
            CONSTRAINT pk_parq_items_inspeccion PRIMARY KEY (id),
            CONSTRAINT uq_parq_items_inspeccion UNIQUE (inspeccion_id, item_catalogo_id),
            CONSTRAINT chk_parq_items_fotos CHECK (jsonb_array_length(fotos) <= 3)
        )
    """)

    _sql("""
        CREATE TABLE parq_historial_acciones (
            id              UUID         NOT NULL DEFAULT gen_random_uuid(),
            tipo_accion     VARCHAR(50)  NOT NULL,
            vehiculo_id     UUID REFERENCES parq_vehiculos(id) ON DELETE CASCADE,
            inspeccion_id   UUID REFERENCES parq_inspecciones(id) ON DELETE CASCADE,
            personal_id     UUID REFERENCES usuarios(id) ON DELETE SET NULL,
            realizado_por   UUID REFERENCES usuarios(id) ON DELETE SET NULL,
            organization_id UUID REFERENCES organizaciones(id) ON DELETE SET NULL,
            ip_address      VARCHAR(45),
            user_agent      VARCHAR(500),
            detalles        JSONB        NOT NULL DEFAULT '{}',
            valor_anterior  JSONB,
            valor_nuevo     JSONB,
            hash_anterior   VARCHAR(64)  NOT NULL DEFAULT '',
            hash_registro   VARCHAR(64)  NOT NULL DEFAULT '',
            creado_en       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            CONSTRAINT pk_parq_historial_acciones PRIMARY KEY (id)
        )
    """)

    # ── Tablas NUNC ────────────────────────────────────────────────────────────
    _sql("""
        CREATE TABLE nunc_sesiones (
            id              UUID         NOT NULL DEFAULT gen_random_uuid(),
            public_id       VARCHAR(40)  UNIQUE NOT NULL,
            codigo_sesion   VARCHAR(10)  UNIQUE NOT NULL DEFAULT '',
            nombre_entidad  VARCHAR(300) NOT NULL,
            nombre_perito   VARCHAR(300) NOT NULL,
            departamento    VARCHAR(10)  NOT NULL,
            municipio       VARCHAR(10)  NOT NULL,
            entidad         VARCHAR(10)  NOT NULL,
            unidad          VARCHAR(10)  NOT NULL,
            ano             VARCHAR(4)   NOT NULL,
            estado          estado_sesion_nunc_enum NOT NULL DEFAULT 'activa',
            expiracion      TIMESTAMPTZ  NOT NULL,
            creado_por      UUID REFERENCES usuarios(id) ON DELETE SET NULL,
            organization_id UUID REFERENCES organizaciones(id) ON DELETE SET NULL,
            creado_en       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            actualizado_en  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            CONSTRAINT pk_nunc_sesiones PRIMARY KEY (id)
        )
    """)

    _sql("""
        CREATE TABLE nunc_registros (
            id                UUID         NOT NULL DEFAULT gen_random_uuid(),
            public_id         VARCHAR(40)  UNIQUE NOT NULL,
            sesion_id         UUID         NOT NULL REFERENCES nunc_sesiones(id) ON DELETE CASCADE,
            numero_secuencial INTEGER      NOT NULL,
            placa             VARCHAR(10)  NOT NULL,
            departamento      VARCHAR(10)  NOT NULL,
            municipio         VARCHAR(10)  NOT NULL,
            entidad           VARCHAR(10)  NOT NULL,
            unidad            VARCHAR(10)  NOT NULL,
            ano               VARCHAR(4)   NOT NULL,
            organization_id   UUID REFERENCES organizaciones(id) ON DELETE SET NULL,
            creado_en         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            CONSTRAINT pk_nunc_registros PRIMARY KEY (id),
            CONSTRAINT uq_nunc_registros_sesion_secuencial UNIQUE (sesion_id, numero_secuencial)
        )
    """)

    # ── Índices Movilidad ──────────────────────────────────────────────────────
    _sql("CREATE INDEX ix_mov_org_nombre    ON mov_organismos_transito (nombre)")
    _sql("CREATE INDEX ix_mov_org_depto     ON mov_organismos_transito (departamento)")
    _sql("CREATE INDEX ix_mov_org_activo    ON mov_organismos_transito (activo)")
    _sql("CREATE INDEX ix_mov_org_search    ON mov_organismos_transito USING GIN (search_vector)")
    _sql("CREATE INDEX ix_mov_cuentas_placa     ON mov_cuentas_vehiculos (placa)")
    _sql("CREATE INDEX ix_mov_cuentas_numero    ON mov_cuentas_vehiculos (numero_cuenta)")
    _sql("CREATE INDEX ix_mov_cuentas_creado_en ON mov_cuentas_vehiculos (creado_en DESC)")
    _sql("CREATE INDEX ix_mov_traslados_cuenta      ON mov_traslados (cuenta_id)")
    _sql("CREATE INDEX ix_mov_traslados_estado      ON mov_traslados (estado)")
    _sql("CREATE INDEX ix_mov_traslados_vencimiento ON mov_traslados (vencimiento)")
    _sql("CREATE INDEX ix_mov_radicaciones_cuenta   ON mov_radicaciones (cuenta_id)")
    _sql("CREATE INDEX ix_mov_radicaciones_estado   ON mov_radicaciones (estado)")
    _sql("CREATE INDEX ix_mov_novedades_proceso ON mov_novedades (proceso_tipo, proceso_id)")
    _sql("CREATE INDEX ix_mov_novedades_estado  ON mov_novedades (estado)")
    _sql("CREATE INDEX ix_mov_historial_cuenta  ON mov_historial_acciones (cuenta_id)")
    _sql("CREATE INDEX ix_mov_historial_ts      ON mov_historial_acciones (creado_en DESC)")

    # ── Índices Parqueadero ────────────────────────────────────────────────────
    _sql("CREATE INDEX ix_parq_veh_placa   ON parq_vehiculos (placa)")
    _sql("CREATE INDEX ix_parq_veh_activo  ON parq_vehiculos (activo)")
    _sql("CREATE INDEX ix_parq_insp_vehiculo ON parq_inspecciones (vehiculo_id)")
    _sql("CREATE INDEX ix_parq_insp_fecha    ON parq_inspecciones (fecha)")
    _sql("CREATE INDEX ix_parq_insp_operador ON parq_inspecciones (operador_id)")

    # ── Índices NUNC ───────────────────────────────────────────────────────────
    _sql("CREATE INDEX ix_nunc_ses_codigo     ON nunc_sesiones (codigo_sesion)")
    _sql("CREATE INDEX ix_nunc_ses_creado_por ON nunc_sesiones (creado_por)")
    _sql("CREATE INDEX ix_nunc_ses_expiracion ON nunc_sesiones (expiracion)")
    _sql("CREATE INDEX ix_nunc_reg_sesion ON nunc_registros (sesion_id)")
    _sql("CREATE INDEX ix_nunc_reg_placa  ON nunc_registros (placa)")

    # ── Funciones SQL ──────────────────────────────────────────────────────────
    _sql("""
        CREATE OR REPLACE FUNCTION es_dia_habil(p_fecha DATE) RETURNS boolean
        LANGUAGE sql STABLE AS $$
            SELECT EXTRACT(DOW FROM p_fecha) NOT IN (0, 6)
            AND NOT EXISTS (SELECT 1 FROM mov_festivos_colombia WHERE fecha = p_fecha);
        $$
    """)

    _sql("""
        CREATE OR REPLACE FUNCTION sumar_dias_habiles(p_fecha_inicio DATE, p_dias INTEGER) RETURNS date
        LANGUAGE plpgsql STABLE AS $$
        DECLARE
            v_fecha DATE := p_fecha_inicio;
            v_count INTEGER := 0;
        BEGIN
            WHILE v_count < p_dias LOOP
                v_fecha := v_fecha + 1;
                IF es_dia_habil(v_fecha) THEN
                    v_count := v_count + 1;
                END IF;
            END LOOP;
            RETURN v_fecha;
        END;
        $$
    """)

    _sql("""
        CREATE OR REPLACE FUNCTION contar_dias_habiles(p_inicio DATE, p_fin DATE) RETURNS integer
        LANGUAGE plpgsql STABLE AS $$
        DECLARE
            v_fecha DATE := p_inicio;
            v_count INTEGER := 0;
            v_signo INTEGER := CASE WHEN p_fin >= p_inicio THEN 1 ELSE -1 END;
        BEGIN
            WHILE v_fecha != p_fin LOOP
                v_fecha := v_fecha + v_signo;
                IF es_dia_habil(v_fecha) THEN
                    v_count := v_count + v_signo;
                END IF;
            END LOOP;
            RETURN v_count;
        END;
        $$
    """)

    _sql("""
        CREATE OR REPLACE FUNCTION generar_numero_cuenta() RETURNS text
        LANGUAGE plpgsql AS $$
        DECLARE
            v_fecha     TEXT := TO_CHAR(NOW(), 'YYYYMMDD');
            v_count     INTEGER;
            v_resultado TEXT;
        BEGIN
            PERFORM pg_advisory_xact_lock(987654321);
            SELECT COUNT(*) INTO v_count
            FROM mov_cuentas_vehiculos
            WHERE numero_cuenta LIKE v_fecha || '-%';
            v_resultado := v_fecha || '-' || LPAD((v_count + 1)::text, 5, '0');
            RETURN v_resultado;
        END;
        $$
    """)

    _sql("""
        CREATE OR REPLACE FUNCTION generar_codigo_nunc() RETURNS text
        LANGUAGE plpgsql AS $$
        DECLARE
            v_chars    TEXT := 'ABCDEFGHJKMNPQRSTUVWXYZ23456789';
            v_codigo   TEXT;
            v_intentos INTEGER := 0;
        BEGIN
            LOOP
                v_codigo := 'PER-';
                FOR i IN 1..6 LOOP
                    v_codigo := v_codigo || substr(v_chars, floor(random() * length(v_chars) + 1)::integer, 1);
                END LOOP;
                EXIT WHEN NOT EXISTS (SELECT 1 FROM nunc_sesiones WHERE codigo_sesion = v_codigo);
                v_intentos := v_intentos + 1;
                IF v_intentos >= 5 THEN
                    RAISE EXCEPTION 'No se pudo generar código único NUNC';
                END IF;
            END LOOP;
            RETURN v_codigo;
        END;
        $$
    """)

    _sql("""
        CREATE OR REPLACE FUNCTION validar_proceso_unico() RETURNS TRIGGER
        LANGUAGE plpgsql AS $$
        DECLARE
            v_estados_terminales_t TEXT[] := ARRAY['trasladado'];
            v_estados_terminales_r TEXT[] := ARRAY['radicado'];
        BEGIN
            IF EXISTS (
                SELECT 1 FROM mov_traslados
                WHERE cuenta_id = NEW.cuenta_id
                AND estado != ALL(v_estados_terminales_t)
                AND id != COALESCE(NEW.id, '00000000-0000-0000-0000-000000000000'::uuid)
            ) OR EXISTS (
                SELECT 1 FROM mov_radicaciones
                WHERE cuenta_id = NEW.cuenta_id
                AND estado != ALL(v_estados_terminales_r)
                AND id != COALESCE(NEW.id, '00000000-0000-0000-0000-000000000000'::uuid)
            ) THEN
                RAISE EXCEPTION 'Ya existe un proceso activo para esta cuenta';
            END IF;
            RETURN NEW;
        END;
        $$
    """)

    _sql("""
        CREATE OR REPLACE FUNCTION fn_trigger_vencimiento_radicacion() RETURNS TRIGGER
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.vencimiento IS NULL THEN
                NEW.vencimiento := sumar_dias_habiles(CURRENT_DATE, 60);
            END IF;
            RETURN NEW;
        END;
        $$
    """)

    _sql("""
        CREATE OR REPLACE FUNCTION fn_trigger_vencimiento_traslado() RETURNS TRIGGER
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.estado = 'aprobado' AND OLD.estado != 'aprobado' THEN
                NEW.aprobado_en := NOW();
                NEW.vencimiento := sumar_dias_habiles(CURRENT_DATE, 60);
            END IF;
            RETURN NEW;
        END;
        $$
    """)

    _sql("""
        CREATE OR REPLACE FUNCTION fn_trigger_marcar_completado() RETURNS TRIGGER
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.estado IN ('trasladado', 'radicado') AND NEW.completado_en IS NULL THEN
                NEW.completado_en := NOW();
            END IF;
            RETURN NEW;
        END;
        $$
    """)

    _sql("""
        CREATE OR REPLACE FUNCTION fn_trigger_generar_numero_cuenta() RETURNS TRIGGER
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.numero_cuenta IS NULL OR NEW.numero_cuenta = '' THEN
                NEW.numero_cuenta := generar_numero_cuenta();
            END IF;
            RETURN NEW;
        END;
        $$
    """)

    _sql("""
        CREATE OR REPLACE FUNCTION fn_trigger_generar_codigo_nunc() RETURNS TRIGGER
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.codigo_sesion IS NULL OR NEW.codigo_sesion = '' THEN
                NEW.codigo_sesion := generar_codigo_nunc();
            END IF;
            RETURN NEW;
        END;
        $$
    """)

    _sql("""
        CREATE OR REPLACE FUNCTION fn_trigger_nunc_secuencial() RETURNS TRIGGER
        LANGUAGE plpgsql AS $$
        BEGIN
            SELECT COALESCE(MAX(numero_secuencial), 0) + 1 INTO NEW.numero_secuencial
            FROM nunc_registros WHERE sesion_id = NEW.sesion_id;
            RETURN NEW;
        END;
        $$
    """)

    _sql("""
        CREATE OR REPLACE FUNCTION fn_trigger_search_organismo() RETURNS TRIGGER
        LANGUAGE plpgsql AS $$
        BEGIN
            NEW.search_vector := to_tsvector('spanish',
                COALESCE(NEW.nombre, '') || ' ' ||
                COALESCE(NEW.municipio, '') || ' ' ||
                COALESCE(NEW.departamento, '')
            );
            RETURN NEW;
        END;
        $$
    """)

    # ── Triggers ───────────────────────────────────────────────────────────────
    _sql("""
        CREATE TRIGGER trg_generar_numero_cuenta
            BEFORE INSERT ON mov_cuentas_vehiculos
            FOR EACH ROW EXECUTE FUNCTION fn_trigger_generar_numero_cuenta()
    """)

    _sql("""
        CREATE TRIGGER trg_vencimiento_radicacion
            BEFORE INSERT ON mov_radicaciones
            FOR EACH ROW EXECUTE FUNCTION fn_trigger_vencimiento_radicacion()
    """)

    _sql("""
        CREATE TRIGGER trg_vencimiento_traslado
            BEFORE UPDATE ON mov_traslados
            FOR EACH ROW EXECUTE FUNCTION fn_trigger_vencimiento_traslado()
    """)

    _sql("""
        CREATE TRIGGER trg_marcar_completado_traslado
            BEFORE UPDATE ON mov_traslados
            FOR EACH ROW EXECUTE FUNCTION fn_trigger_marcar_completado()
    """)

    _sql("""
        CREATE TRIGGER trg_marcar_completado_radicacion
            BEFORE UPDATE ON mov_radicaciones
            FOR EACH ROW EXECUTE FUNCTION fn_trigger_marcar_completado()
    """)

    _sql("""
        CREATE TRIGGER trg_validar_proceso_unico_traslado
            BEFORE INSERT ON mov_traslados
            FOR EACH ROW EXECUTE FUNCTION validar_proceso_unico()
    """)

    _sql("""
        CREATE TRIGGER trg_validar_proceso_unico_radicacion
            BEFORE INSERT ON mov_radicaciones
            FOR EACH ROW EXECUTE FUNCTION validar_proceso_unico()
    """)

    _sql("""
        CREATE TRIGGER trg_search_organismo
            BEFORE INSERT OR UPDATE ON mov_organismos_transito
            FOR EACH ROW EXECUTE FUNCTION fn_trigger_search_organismo()
    """)

    _sql("""
        CREATE TRIGGER trg_generar_codigo_nunc
            BEFORE INSERT ON nunc_sesiones
            FOR EACH ROW EXECUTE FUNCTION fn_trigger_generar_codigo_nunc()
    """)

    _sql("""
        CREATE TRIGGER trg_nunc_secuencial
            BEFORE INSERT ON nunc_registros
            FOR EACH ROW EXECUTE FUNCTION fn_trigger_nunc_secuencial()
    """)

    # Triggers actualizado_en — reusar fn_actualizar_actualizado_en de migración 001
    for tabla in (
        "mov_organismos_transito",
        "mov_empresas_transporte",
        "mov_cuentas_vehiculos",
        "mov_traslados",
        "mov_radicaciones",
        "mov_novedades",
        "mov_notificaciones_radicacion",
        "parq_vehiculos",
        "parq_datos_personal",
        "parq_items_catalogo",
        "parq_inspecciones",
        "nunc_sesiones",
    ):
        _sql(f"DROP TRIGGER IF EXISTS trg_actualizado_en ON {tabla}")
        _sql(f"""
            CREATE TRIGGER trg_actualizado_en
                BEFORE UPDATE ON {tabla}
                FOR EACH ROW EXECUTE FUNCTION fn_actualizar_actualizado_en()
        """)

    # ── RLS — tablas con política estándar de tenant ───────────────────────────
    _RLS_TENANT = (
        "fn_tenant_id() = '' OR organization_id IS NULL OR organization_id::text = fn_tenant_id()"
    )
    for tabla, policy in (
        ("mov_organismos_transito", "rls_mov_org"),
        ("mov_empresas_transporte", "rls_mov_emp"),
        ("mov_cuentas_vehiculos",   "rls_mov_cuentas"),
        ("mov_traslados",           "rls_mov_traslados"),
        ("mov_radicaciones",        "rls_mov_radicaciones"),
        ("mov_novedades",           "rls_mov_novedades"),
        ("mov_historial_acciones",  "rls_mov_historial"),
        ("parq_vehiculos",          "rls_parq_veh"),
        ("parq_datos_personal",     "rls_parq_personal"),
        ("parq_inspecciones",       "rls_parq_insp"),
        ("nunc_sesiones",           "rls_nunc_ses"),
        ("nunc_registros",          "rls_nunc_reg"),
    ):
        _sql(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")
        _sql(f"ALTER TABLE {tabla} FORCE  ROW LEVEL SECURITY")
        _sql(f"""
            CREATE POLICY {policy} ON {tabla} FOR ALL
                USING ({_RLS_TENANT})
                WITH CHECK ({_RLS_TENANT})
        """)

    # Festivos: lectura para todos, escritura solo admin
    _sql("ALTER TABLE mov_festivos_colombia ENABLE ROW LEVEL SECURITY")
    _sql("ALTER TABLE mov_festivos_colombia FORCE  ROW LEVEL SECURITY")
    _sql("CREATE POLICY rls_festivos_leer       ON mov_festivos_colombia FOR SELECT USING (true)")
    _sql("CREATE POLICY rls_festivos_escribir   ON mov_festivos_colombia FOR INSERT WITH CHECK (fn_tenant_id() = '' OR fn_es_admin())")
    _sql("CREATE POLICY rls_festivos_actualizar ON mov_festivos_colombia FOR UPDATE USING (fn_tenant_id() = '' OR fn_es_admin())")
    _sql("CREATE POLICY rls_festivos_eliminar   ON mov_festivos_colombia FOR DELETE USING (fn_tenant_id() = '' OR fn_es_admin())")

    # Items catálogo: lectura global, escritura solo admin
    _sql("ALTER TABLE parq_items_catalogo ENABLE ROW LEVEL SECURITY")
    _sql("ALTER TABLE parq_items_catalogo FORCE  ROW LEVEL SECURITY")
    _sql("CREATE POLICY rls_parq_cat_leer       ON parq_items_catalogo FOR SELECT USING (true)")
    _sql("CREATE POLICY rls_parq_cat_escribir   ON parq_items_catalogo FOR INSERT WITH CHECK (fn_tenant_id() = '' OR fn_es_admin())")
    _sql("CREATE POLICY rls_parq_cat_actualizar ON parq_items_catalogo FOR UPDATE USING (fn_tenant_id() = '' OR fn_es_admin())")

    # ── Seed: permisos módulos movilidad, parqueadero y NUNC ──────────────────
    _sql("""
        INSERT INTO permisos (id, recurso, accion, descripcion) VALUES
            (gen_random_uuid(), 'movilidad.cuentas',       'crear',    'Crear cuentas de vehículos'),
            (gen_random_uuid(), 'movilidad.cuentas',       'leer',     'Ver cuentas y vehículos'),
            (gen_random_uuid(), 'movilidad.cuentas',       'editar',   'Editar datos de cuentas'),
            (gen_random_uuid(), 'movilidad.traslados',     'crear',    'Crear traslados'),
            (gen_random_uuid(), 'movilidad.traslados',     'leer',     'Ver traslados'),
            (gen_random_uuid(), 'movilidad.traslados',     'aprobar',  'Aprobar y cambiar estado de traslados'),
            (gen_random_uuid(), 'movilidad.radicaciones',  'crear',    'Crear radicaciones'),
            (gen_random_uuid(), 'movilidad.radicaciones',  'leer',     'Ver radicaciones'),
            (gen_random_uuid(), 'movilidad.radicaciones',  'revisar',  'Revisar y cambiar estado de radicaciones'),
            (gen_random_uuid(), 'movilidad.novedades',     'crear',    'Crear novedades'),
            (gen_random_uuid(), 'movilidad.novedades',     'resolver', 'Resolver novedades'),
            (gen_random_uuid(), 'movilidad.reportes',      'leer',     'Ver reportes de movilidad'),
            (gen_random_uuid(), 'movilidad.reportes',      'exportar', 'Exportar reportes de movilidad'),
            (gen_random_uuid(), 'parqueadero.vehiculos',   'gestionar','Gestionar vehículos de parqueadero'),
            (gen_random_uuid(), 'parqueadero.personal',    'gestionar','Gestionar personal de parqueadero'),
            (gen_random_uuid(), 'parqueadero.inspecciones','crear',    'Crear inspecciones preoperacionales'),
            (gen_random_uuid(), 'parqueadero.inspecciones','aprobar',  'Aprobar inspecciones'),
            (gen_random_uuid(), 'parqueadero.reportes',    'leer',     'Ver reportes de parqueadero'),
            (gen_random_uuid(), 'nunc.sesiones',           'crear',    'Crear sesiones NUNC'),
            (gen_random_uuid(), 'nunc.registros',          'crear',    'Crear registros NUNC'),
            (gen_random_uuid(), 'nunc.reportes',           'leer',     'Ver reportes NUNC')
        ON CONFLICT (recurso, accion) DO NOTHING
    """)

    # ── Seed: festivos colombianos 2024-2026 ───────────────────────────────────
    _sql("""
        INSERT INTO mov_festivos_colombia (fecha, nombre, tipo) VALUES
            -- 2024
            ('2024-01-01', 'Año Nuevo',                  'civil'),
            ('2024-01-08', 'Reyes Magos',                'religioso'),
            ('2024-03-25', 'San José',                   'religioso'),
            ('2024-03-28', 'Jueves Santo',               'religioso'),
            ('2024-03-29', 'Viernes Santo',              'religioso'),
            ('2024-05-01', 'Día del Trabajo',            'civil'),
            ('2024-05-13', 'Ascensión del Señor',        'religioso'),
            ('2024-06-03', 'Corpus Christi',             'religioso'),
            ('2024-06-10', 'Sagrado Corazón',            'religioso'),
            ('2024-07-01', 'San Pedro y San Pablo',      'religioso'),
            ('2024-07-20', 'Independencia de Colombia',  'civil'),
            ('2024-08-07', 'Batalla de Boyacá',          'civil'),
            ('2024-08-19', 'Asunción de María',          'religioso'),
            ('2024-10-14', 'Día de la Raza',             'civil'),
            ('2024-11-04', 'Todos los Santos',           'religioso'),
            ('2024-11-11', 'Independencia de Cartagena', 'civil'),
            ('2024-12-08', 'Inmaculada Concepción',      'religioso'),
            ('2024-12-25', 'Navidad',                    'religioso'),
            -- 2025
            ('2025-01-01', 'Año Nuevo',                  'civil'),
            ('2025-01-06', 'Reyes Magos',                'religioso'),
            ('2025-03-24', 'San José',                   'religioso'),
            ('2025-04-17', 'Jueves Santo',               'religioso'),
            ('2025-04-18', 'Viernes Santo',              'religioso'),
            ('2025-05-01', 'Día del Trabajo',            'civil'),
            ('2025-06-02', 'Ascensión del Señor',        'religioso'),
            ('2025-06-23', 'Corpus Christi',             'religioso'),
            ('2025-06-30', 'Sagrado Corazón',            'religioso'),
            ('2025-06-30', 'San Pedro y San Pablo',      'religioso'),
            ('2025-07-20', 'Independencia de Colombia',  'civil'),
            ('2025-08-07', 'Batalla de Boyacá',          'civil'),
            ('2025-08-18', 'Asunción de María',          'religioso'),
            ('2025-10-13', 'Día de la Raza',             'civil'),
            ('2025-11-03', 'Todos los Santos',           'religioso'),
            ('2025-11-17', 'Independencia de Cartagena', 'civil'),
            ('2025-12-08', 'Inmaculada Concepción',      'religioso'),
            ('2025-12-25', 'Navidad',                    'religioso'),
            -- 2026
            ('2026-01-01', 'Año Nuevo',                  'civil'),
            ('2026-01-12', 'Reyes Magos',                'religioso'),
            ('2026-03-23', 'San José',                   'religioso'),
            ('2026-04-02', 'Jueves Santo',               'religioso'),
            ('2026-04-03', 'Viernes Santo',              'religioso'),
            ('2026-05-01', 'Día del Trabajo',            'civil'),
            ('2026-05-18', 'Ascensión del Señor',        'religioso'),
            ('2026-06-08', 'Corpus Christi',             'religioso'),
            ('2026-06-15', 'Sagrado Corazón',            'religioso'),
            ('2026-07-06', 'San Pedro y San Pablo',      'religioso'),
            ('2026-07-20', 'Independencia de Colombia',  'civil'),
            ('2026-08-07', 'Batalla de Boyacá',          'civil'),
            ('2026-08-17', 'Asunción de María',          'religioso'),
            ('2026-10-12', 'Día de la Raza',             'civil'),
            ('2026-11-02', 'Todos los Santos',           'religioso'),
            ('2026-11-16', 'Independencia de Cartagena', 'civil'),
            ('2026-12-08', 'Inmaculada Concepción',      'religioso'),
            ('2026-12-25', 'Navidad',                    'religioso')
        ON CONFLICT (fecha) DO NOTHING
    """)


def downgrade() -> None:

    # ── Triggers (cada trigger solo en la tabla donde existe) ─────────────────
    # trg_actualizado_en — tablas con columna actualizado_en
    for tabla in (
        "mov_organismos_transito", "mov_empresas_transporte", "mov_cuentas_vehiculos",
        "mov_traslados", "mov_radicaciones", "mov_novedades", "mov_notificaciones_radicacion",
        "parq_vehiculos", "parq_datos_personal", "parq_items_catalogo", "parq_inspecciones",
        "nunc_sesiones",
    ):
        _sql(f"DROP TRIGGER IF EXISTS trg_actualizado_en ON {tabla}")

    _sql("DROP TRIGGER IF EXISTS trg_generar_numero_cuenta          ON mov_cuentas_vehiculos")
    _sql("DROP TRIGGER IF EXISTS trg_vencimiento_radicacion         ON mov_radicaciones")
    _sql("DROP TRIGGER IF EXISTS trg_vencimiento_traslado           ON mov_traslados")
    _sql("DROP TRIGGER IF EXISTS trg_marcar_completado_traslado     ON mov_traslados")
    _sql("DROP TRIGGER IF EXISTS trg_marcar_completado_radicacion   ON mov_radicaciones")
    _sql("DROP TRIGGER IF EXISTS trg_validar_proceso_unico_traslado    ON mov_traslados")
    _sql("DROP TRIGGER IF EXISTS trg_validar_proceso_unico_radicacion  ON mov_radicaciones")
    _sql("DROP TRIGGER IF EXISTS trg_search_organismo               ON mov_organismos_transito")
    _sql("DROP TRIGGER IF EXISTS trg_generar_codigo_nunc            ON nunc_sesiones")
    _sql("DROP TRIGGER IF EXISTS trg_nunc_secuencial                ON nunc_registros")

    # ── Funciones ──────────────────────────────────────────────────────────────
    _sql("DROP FUNCTION IF EXISTS fn_trigger_search_organismo()")
    _sql("DROP FUNCTION IF EXISTS fn_trigger_nunc_secuencial()")
    _sql("DROP FUNCTION IF EXISTS fn_trigger_generar_codigo_nunc()")
    _sql("DROP FUNCTION IF EXISTS fn_trigger_generar_numero_cuenta()")
    _sql("DROP FUNCTION IF EXISTS fn_trigger_marcar_completado()")
    _sql("DROP FUNCTION IF EXISTS fn_trigger_vencimiento_traslado()")
    _sql("DROP FUNCTION IF EXISTS fn_trigger_vencimiento_radicacion()")
    _sql("DROP FUNCTION IF EXISTS validar_proceso_unico()")
    _sql("DROP FUNCTION IF EXISTS generar_codigo_nunc()")
    _sql("DROP FUNCTION IF EXISTS generar_numero_cuenta()")
    _sql("DROP FUNCTION IF EXISTS contar_dias_habiles(DATE, DATE)")
    _sql("DROP FUNCTION IF EXISTS sumar_dias_habiles(DATE, INTEGER)")
    _sql("DROP FUNCTION IF EXISTS es_dia_habil(DATE)")

    # ── Políticas RLS + desactivar RLS ────────────────────────────────────────
    for tabla, politica in (
        ("nunc_registros",          "rls_nunc_reg"),
        ("nunc_sesiones",           "rls_nunc_ses"),
        ("parq_items_catalogo",     "rls_parq_cat_leer"),
        ("parq_items_catalogo",     "rls_parq_cat_escribir"),
        ("parq_items_catalogo",     "rls_parq_cat_actualizar"),
        ("parq_inspecciones",       "rls_parq_insp"),
        ("parq_datos_personal",     "rls_parq_personal"),
        ("parq_vehiculos",          "rls_parq_veh"),
        ("mov_festivos_colombia",   "rls_festivos_leer"),
        ("mov_festivos_colombia",   "rls_festivos_escribir"),
        ("mov_festivos_colombia",   "rls_festivos_actualizar"),
        ("mov_festivos_colombia",   "rls_festivos_eliminar"),
        ("mov_historial_acciones",  "rls_mov_historial"),
        ("mov_novedades",           "rls_mov_novedades"),
        ("mov_radicaciones",        "rls_mov_radicaciones"),
        ("mov_traslados",           "rls_mov_traslados"),
        ("mov_cuentas_vehiculos",   "rls_mov_cuentas"),
        ("mov_empresas_transporte", "rls_mov_emp"),
        ("mov_organismos_transito", "rls_mov_org"),
    ):
        _sql(f"DROP POLICY IF EXISTS {politica} ON {tabla}")

    for tabla in (
        "nunc_registros",
        "nunc_sesiones",
        "parq_items_catalogo",
        "parq_inspecciones",
        "parq_datos_personal",
        "parq_vehiculos",
        "mov_festivos_colombia",
        "mov_historial_acciones",
        "mov_novedades",
        "mov_notificaciones_radicacion",
        "mov_radicaciones",
        "mov_traslados",
        "mov_cuentas_vehiculos",
        "mov_empresas_transporte",
        "mov_organismos_transito",
    ):
        _sql(f"ALTER TABLE IF EXISTS {tabla} DISABLE ROW LEVEL SECURITY")

    # ── Tablas (orden inverso a FK) ────────────────────────────────────────────
    _sql("DROP TABLE IF EXISTS nunc_registros                CASCADE")
    _sql("DROP TABLE IF EXISTS nunc_sesiones                 CASCADE")
    _sql("DROP TABLE IF EXISTS parq_historial_acciones       CASCADE")
    _sql("DROP TABLE IF EXISTS parq_items_inspeccion         CASCADE")
    _sql("DROP TABLE IF EXISTS parq_inspecciones             CASCADE")
    _sql("DROP TABLE IF EXISTS parq_items_catalogo           CASCADE")
    _sql("DROP TABLE IF EXISTS parq_datos_personal           CASCADE")
    _sql("DROP TABLE IF EXISTS parq_vehiculos                CASCADE")
    _sql("DROP TABLE IF EXISTS mov_historial_acciones        CASCADE")
    _sql("DROP TABLE IF EXISTS mov_adjuntos_novedades        CASCADE")
    _sql("DROP TABLE IF EXISTS mov_novedades                 CASCADE")
    _sql("DROP TABLE IF EXISTS mov_notificaciones_radicacion CASCADE")
    _sql("DROP TABLE IF EXISTS mov_radicaciones              CASCADE")
    _sql("DROP TABLE IF EXISTS mov_traslados                 CASCADE")
    _sql("DROP TABLE IF EXISTS mov_cuentas_vehiculos         CASCADE")
    _sql("DROP TABLE IF EXISTS mov_empresas_transporte       CASCADE")
    _sql("DROP TABLE IF EXISTS mov_organismos_transito       CASCADE")
    _sql("DROP TABLE IF EXISTS mov_festivos_colombia         CASCADE")

    # ── Enums ──────────────────────────────────────────────────────────────────
    _sql("DROP TYPE IF EXISTS estado_sesion_nunc_enum")
    _sql("DROP TYPE IF EXISTS tipo_vehiculo_parqueadero_enum")
    _sql("DROP TYPE IF EXISTS estado_item_enum")
    _sql("DROP TYPE IF EXISTS turno_inspeccion_enum")
    _sql("DROP TYPE IF EXISTS tipo_festivo_enum")
    _sql("DROP TYPE IF EXISTS estado_novedad_enum")
    _sql("DROP TYPE IF EXISTS prioridad_novedad_enum")
    _sql("DROP TYPE IF EXISTS tipo_novedad_enum")
    _sql("DROP TYPE IF EXISTS estado_radicacion_enum")
    _sql("DROP TYPE IF EXISTS estado_traslado_enum")
    _sql("DROP TYPE IF EXISTS tipo_servicio_enum")
