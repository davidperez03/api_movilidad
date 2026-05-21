"""Agregar estado devuelto a traslados y radicaciones

revision : 003
revises  : 002
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels = None
depends_on = None


def _sql(s: str) -> None:
    op.execute(sa.text(s))


def upgrade() -> None:
    # PostgreSQL no permite eliminar valores de un enum, pero sí agregar.
    # ALTER TYPE ... ADD VALUE es idempotente con IF NOT EXISTS (PG >= 9.6).
    _sql("ALTER TYPE estado_traslado_enum  ADD VALUE IF NOT EXISTS 'devuelto'")
    _sql("ALTER TYPE estado_radicacion_enum ADD VALUE IF NOT EXISTS 'devuelto'")


def downgrade() -> None:
    # No se puede eliminar valores de un enum en PostgreSQL sin recrearlo.
    # Para rollback, recrear el enum sin 'devuelto' requeriría migrar los datos
    # existentes — se deja documentado pero no implementado.
    pass
