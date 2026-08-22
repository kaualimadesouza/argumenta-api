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
"""Issue #10 could write duplicated beats, which the CREATE UNIQUE INDEX below
would fail on. Edited into this revision on purpose: the dedup has to run before
the index. Soft delete keeping the oldest live row, id breaking ties."""


def upgrade() -> None:
    # a rollback pins the previous image and keeps this schema: that release
    # names this index in on_conflict_do_nothing, so dropping it turns every
    # reaction into a 42P10 error
    op.add_column(
        'character_reactions',
        sa.Column(
            'input_tokens',
            sa.Integer(),
            nullable=True,
            comment='prompt da reacao domina o custo',
        ),
    )
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
