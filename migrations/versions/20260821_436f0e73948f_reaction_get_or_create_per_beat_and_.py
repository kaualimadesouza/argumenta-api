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


def upgrade() -> None:
    # expand only: a nullable column plus the partial unique that turns the
    # reaction get-or-create into a database guarantee instead of a race
    op.add_column(
        'character_reactions',
        sa.Column(
            'input_tokens',
            sa.Integer(),
            nullable=True,
            comment='prompt da reacao domina o custo',
        ),
    )
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
