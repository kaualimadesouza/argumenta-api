"""retire frozen fallback reactions

Revision ID: 9e16860b95a2
Revises: bfb23f323d3f
Create Date: 2026-08-22 17:24:47.530381

"""

from collections.abc import Sequence

from alembic import op

revision: str = "9e16860b95a2"  # pragma: allowlist secret
down_revision: str | None = "bfb23f323d3f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


RETIRE_FALLBACK_LINES = """
UPDATE character_reactions
SET deleted_at = now(), updated_at = now()
WHERE deleted_at IS NULL AND model = 'fallback'
"""
"""Issue #10 persisted the scripted line as model = 'fallback', so one API
outage froze a generic answer forever. Retiring the row makes the beat
regenerable: the endpoint only reads live rows."""


def upgrade() -> None:
    # a revision of its own, and not folded into 436f0e73948f where the bug was
    # introduced, because a database already stamped with that revision would
    # never run the fix
    op.execute(RETIRE_FALLBACK_LINES)


def downgrade() -> None:
    """Nothing to undo: the rows are soft deleted, and resurrecting them would
    restore the frozen line this revision exists to clear."""
