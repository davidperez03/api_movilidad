"""Módulo de inventarios parqueadero

revision : 004
revises  : 003
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: str | None = "003"
branch_labels = None
depends_on = None


def _sql(s: str) -> None:
    op.execute(sa.text(s))


def upgrade() -> None:

    # ── Enums ──────────────────────────────────────────────────────────────────
    _sql("""
        DO $$ BEGIN
            CREATE TYPE tipo_tracking_enum AS ENUM ('ubicacion', 'rango');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$
    """)
    _sql("""
        DO $$ BEGIN
            CREATE TYPE tipo_movimiento_enum AS ENUM ('ingreso', 'traslado');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$
    """)

    # ── Catálogo de insumos ───────────────────────────────────────────────────
    _sql("""
        CREATE TABLE IF NOT EXISTS inv_insumos (
            id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            public_id      VARCHAR(40) UNIQUE NOT NULL,
            nombre         TEXT        NOT NULL,
            categoria      TEXT        NOT NULL,
            unidad         TEXT        NOT NULL,
            stock_minimo   INTEGER     NOT NULL DEFAULT 0 CHECK (stock_minimo >= 0),
            tipo_tracking  tipo_tracking_enum NOT NULL DEFAULT 'ubicacion',
            modulo         TEXT        NOT NULL DEFAULT 'parqueadero',
            activo         BOOLEAN     NOT NULL DEFAULT true,
            organization_id UUID REFERENCES organizaciones(id) ON DELETE SET NULL,
            creado_por     UUID REFERENCES usuarios(id) ON DELETE SET NULL,
            creado_en      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    _sql("CREATE INDEX IF NOT EXISTS idx_inv_insumos_modulo    ON inv_insumos(modulo)")
    _sql("CREATE INDEX IF NOT EXISTS idx_inv_insumos_categoria ON inv_insumos(categoria)")
    _sql("CREATE INDEX IF NOT EXISTS idx_inv_insumos_activo    ON inv_insumos(activo)")
    _sql("CREATE INDEX IF NOT EXISTS idx_inv_insumos_org       ON inv_insumos(organization_id)")

    # ── Stock por ubicación ───────────────────────────────────────────────────
    _sql("""
        CREATE TABLE IF NOT EXISTS inv_stock (
            item_id    UUID        NOT NULL REFERENCES inv_insumos(id) ON DELETE CASCADE,
            modulo     TEXT        NOT NULL,
            ubicacion  TEXT        NOT NULL,
            cantidad   INTEGER     NOT NULL DEFAULT 0 CHECK (cantidad >= 0),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (item_id, modulo, ubicacion)
        )
    """)
    _sql("CREATE INDEX IF NOT EXISTS idx_inv_stock_item    ON inv_stock(item_id)")
    _sql("CREATE INDEX IF NOT EXISTS idx_inv_stock_modulo  ON inv_stock(modulo)")
    _sql("CREATE INDEX IF NOT EXISTS idx_inv_stock_ubicacion ON inv_stock(ubicacion)")

    # ── Rangos numéricos ──────────────────────────────────────────────────────
    _sql("""
        CREATE TABLE IF NOT EXISTS inv_rangos (
            id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            item_id      UUID        NOT NULL UNIQUE REFERENCES inv_insumos(id) ON DELETE CASCADE,
            rango_inicio INTEGER     NOT NULL CHECK (rango_inicio >= 0),
            rango_fin    INTEGER     NOT NULL,
            usados       INTEGER     NOT NULL DEFAULT 0 CHECK (usados >= 0),
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_by   UUID REFERENCES usuarios(id) ON DELETE SET NULL,
            CONSTRAINT chk_inv_rangos_fin     CHECK (rango_fin  >= rango_inicio),
            CONSTRAINT chk_inv_rangos_usados  CHECK (usados     <= rango_fin)
        )
    """)

    # ── Movimientos (log inmutable) ───────────────────────────────────────────
    _sql("""
        CREATE TABLE IF NOT EXISTS inv_movimientos (
            id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            item_id        UUID        NOT NULL REFERENCES inv_insumos(id) ON DELETE RESTRICT,
            modulo         TEXT        NOT NULL,
            tipo           tipo_movimiento_enum NOT NULL,
            origen         TEXT,
            destino        TEXT        NOT NULL,
            cantidad       INTEGER     NOT NULL CHECK (cantidad > 0),
            notas          TEXT,
            creado_por     UUID REFERENCES usuarios(id) ON DELETE SET NULL,
            organization_id UUID REFERENCES organizaciones(id) ON DELETE SET NULL,
            creado_en      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            hash_anterior  TEXT,
            hash_registro  TEXT
        )
    """)
    _sql("CREATE INDEX IF NOT EXISTS idx_inv_mov_item      ON inv_movimientos(item_id)")
    _sql("CREATE INDEX IF NOT EXISTS idx_inv_mov_modulo    ON inv_movimientos(modulo)")
    _sql("CREATE INDEX IF NOT EXISTS idx_inv_mov_fecha     ON inv_movimientos(creado_en DESC)")
    _sql("CREATE INDEX IF NOT EXISTS idx_inv_mov_creado_por ON inv_movimientos(creado_por)")
    _sql("CREATE INDEX IF NOT EXISTS idx_inv_mov_org       ON inv_movimientos(organization_id)")

    # ── Cierres de turno parqueadero ──────────────────────────────────────────
    _sql("""
        CREATE TABLE IF NOT EXISTS parq_inv_cierres (
            id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            vehiculo_id UUID        NOT NULL REFERENCES parq_vehiculos(id) ON DELETE RESTRICT,
            fecha       DATE        NOT NULL DEFAULT current_date,
            creado_por  UUID REFERENCES usuarios(id) ON DELETE SET NULL,
            organization_id UUID REFERENCES organizaciones(id) ON DELETE SET NULL,
            creado_en   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (vehiculo_id, fecha)
        )
    """)
    _sql("CREATE INDEX IF NOT EXISTS idx_parq_inv_cierres_vehiculo ON parq_inv_cierres(vehiculo_id)")
    _sql("CREATE INDEX IF NOT EXISTS idx_parq_inv_cierres_fecha    ON parq_inv_cierres(fecha DESC)")

    _sql("""
        CREATE TABLE IF NOT EXISTS parq_inv_cierres_detalle (
            id                 UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
            cierre_id          UUID    NOT NULL REFERENCES parq_inv_cierres(id) ON DELETE CASCADE,
            item_id            UUID    NOT NULL REFERENCES inv_insumos(id) ON DELETE RESTRICT,
            cantidad_inicial   INTEGER NOT NULL CHECK (cantidad_inicial   >= 0),
            cantidad_final     INTEGER NOT NULL CHECK (cantidad_final     >= 0),
            cantidad_consumida INTEGER GENERATED ALWAYS AS (cantidad_inicial - cantidad_final) STORED,
            UNIQUE (cierre_id, item_id),
            CHECK  (cantidad_final <= cantidad_inicial)
        )
    """)

    # ── Trigger actualizado_en en insumos ─────────────────────────────────────
    _sql("DROP TRIGGER IF EXISTS trg_actualizado_en ON inv_insumos")
    _sql("""
        CREATE TRIGGER trg_actualizado_en
            BEFORE UPDATE ON inv_insumos
            FOR EACH ROW EXECUTE FUNCTION fn_actualizar_actualizado_en()
    """)

    # ── RLS ───────────────────────────────────────────────────────────────────
    _RLS = "fn_tenant_id() = '' OR organization_id IS NULL OR organization_id::text = fn_tenant_id()"

    for tabla, policy in (
        ("inv_insumos",     "rls_inv_insumos"),
        ("inv_movimientos", "rls_inv_movimientos"),
        ("parq_inv_cierres","rls_parq_inv_cierres"),
    ):
        _sql(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")
        _sql(f"ALTER TABLE {tabla} FORCE  ROW LEVEL SECURITY")
        _sql(f"CREATE POLICY {policy} ON {tabla} FOR ALL USING ({_RLS}) WITH CHECK ({_RLS})")

    # inv_stock e inv_rangos no tienen organization_id — policy abierta
    for tabla, policy in (
        ("inv_stock",  "rls_inv_stock"),
        ("inv_rangos", "rls_inv_rangos"),
    ):
        _sql(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")
        _sql(f"ALTER TABLE {tabla} FORCE  ROW LEVEL SECURITY")
        _sql(f"CREATE POLICY {policy} ON {tabla} FOR ALL USING (true) WITH CHECK (true)")


def downgrade() -> None:
    for tabla, policy in (
        ("inv_stock",           "rls_inv_stock"),
        ("inv_rangos",          "rls_inv_rangos"),
        ("inv_insumos",         "rls_inv_insumos"),
        ("inv_movimientos",     "rls_inv_movimientos"),
        ("parq_inv_cierres",    "rls_parq_inv_cierres"),
    ):
        _sql(f"DROP POLICY IF EXISTS {policy} ON {tabla}")

    for tabla in ("parq_inv_cierres_detalle", "parq_inv_cierres",
                  "inv_movimientos", "inv_rangos", "inv_stock", "inv_insumos"):
        _sql(f"DROP TABLE IF EXISTS {tabla} CASCADE")

    _sql("DROP TYPE IF EXISTS tipo_movimiento_enum")
    _sql("DROP TYPE IF EXISTS tipo_tracking_enum")
