"""reaction get-or-create per beat and input tokens

Revision ID: 436f0e73948f
Revises: c3127ce63329
Create Date: 2026-08-21 21:55:22.904768

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '436f0e73948f'  # pragma: allowlist secret
down_revision: str | None = 'c3127ce63329'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


RETIRE_FALLBACK_LINES = """
UPDATE character_reactions
SET deleted_at = now(), updated_at = now()
WHERE deleted_at IS NULL AND model = 'fallback'
"""
"""The first release persisted the scripted line as model = 'fallback', so a ten
minute API outage froze a generic answer forever. Retiring those rows lets the
real reaction be generated again."""

RETIRE_DUPLICATE_BEATS = """
UPDATE character_reactions AS duplicate
SET deleted_at = now(), updated_at = now()
WHERE duplicate.deleted_at IS NULL
  AND EXISTS (
      SELECT 1
      FROM character_reactions AS kept
      WHERE kept.submission_id = duplicate.submission_id
        AND kept.beat = duplicate.beat
        AND kept.deleted_at IS NULL
        AND (kept.created_at, kept.id) < (duplicate.created_at, duplicate.id)
  )
"""
"""The release before this one had no unique index and a get-or-create race, so
duplicated beats are producible by the code currently deployed. Without this the
CREATE UNIQUE INDEX below fails on live data, and since the deploy runs
`alembic upgrade head` before switching traffic, every retry would fail the same
way and the old container would keep serving the bug. Soft delete, keeping the
oldest row: that is the line the student already read."""


def upgrade() -> None:
    # NOT expand only: the partial unique narrows what the release still running
    # is allowed to write, which makes this a contract step. Rolling back by
    # pinning the previous image is not enough here, because the old find()
    # ends in one_or_none() and several beats per submission would raise;
    # a rollback has to downgrade this revision too.
    op.add_column(
        'character_reactions',
        sa.Column(
            'input_tokens',
            sa.Integer(),
            nullable=True,
            comment='prompt da reacao domina o custo',
        ),
    )
    op.execute(RETIRE_FALLBACK_LINES)
    op.execute(RETIRE_DUPLICATE_BEATS)
    op.create_index(
        'uq_character_reactions_submission_beat',
        'character_reactions',
        ['submission_id', 'beat'],
        unique=True,
        postgresql_where=sa.text('deleted_at IS NULL'),
    )


def downgrade() -> None:
    op.drop_index(
        'uq_character_reactions_submission_beat',
        table_name='character_reactions',
        postgresql_where=sa.text('deleted_at IS NULL'),
    )
    op.drop_column('character_reactions', 'input_tokens')
