"""${message}

╔══════════════════════════════════════════════════════════════════╗
║  MIGRATION METADATA                                              ║
╠══════════════════════════════════════════════════════════════════╣
║  Revision  : ${up_revision}${"                                                " | n}║
║  Revises   : ${down_revision | comma,n}${"                                                " | n}║
║  Created   : ${create_date}${"                                                " | n}║
╚══════════════════════════════════════════════════════════════════╝

DESCRIPTION
-----------
<Describe the purpose of this migration here. Be explicit:>
<  - What tables/columns are added, modified, or removed>
<  - Why this change is needed (feature, fix, compliance)>
<  - Any data migration steps required>
<  - Rollback risks or irreversible operations>

CHECKLIST BEFORE APPLYING
--------------------------
  [ ] Tested on staging database
  [ ] Downgrade path verified
  [ ] No breaking changes to running application
  [ ] Indexes analyzed for query impact

ROLLBACK NOTES
--------------
  Run: alembic downgrade ${down_revision | comma,n}
  Risk: <describe data loss or side effects if any>
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
${imports if imports else ""}

# ─── Revision chain ───────────────────────────────────────────────────────────
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}
# ──────────────────────────────────────────────────────────────────────────────


def upgrade() -> None:
    """Apply this migration forward."""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """Revert this migration completely."""
    ${downgrades if downgrades else "pass"}
