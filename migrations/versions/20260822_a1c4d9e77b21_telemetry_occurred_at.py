"""client time on telemetry events

Revision ID: a1c4d9e77b21
Revises: bfb23f323d3f
Create Date: 2026-08-22 14:10:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'a1c4d9e77b21'  # pragma: allowlist secret
down_revision: str | None = 'bfb23f323d3f'  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # expand only: nullable, so the rows written before this keep meaning
    # "client time unknown" instead of claiming the flush time was the event time
    op.add_column(
        'telemetry_events',
        sa.Column(
            'occurred_at',
            postgresql.TIMESTAMP(timezone=True),
            nullable=True,
            comment='hora no cliente; created_at e a hora do flush',
        ),
    )


def downgrade() -> None:
    op.drop_column('telemetry_events', 'occurred_at')
