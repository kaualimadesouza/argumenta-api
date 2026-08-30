"""add submission status for async evaluation

Revision ID: 2307c684b7f8
Revises: 9dbe20c77d6c
Create Date: 2026-08-29 22:30:37.417944

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2307c684b7f8"  # pragma: allowlist secret
down_revision: str | None = "9dbe20c77d6c"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

submission_status = sa.Enum("evaluating", "evaluated", "failed", name="submission_status")


def upgrade() -> None:
    submission_status.create(op.get_bind())
    # backfill default: every pre-async row already carries its evaluation
    # (a timed-out synchronous request rolled back entirely, issue #68)
    op.add_column(
        "submissions",
        sa.Column("status", submission_status, server_default="evaluated", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("submissions", "status")
    submission_status.drop(op.get_bind())
