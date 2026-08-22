"""store the exam lens with each evaluation

Revision ID: bfb23f323d3f
Revises: 436f0e73948f
Create Date: 2026-08-21 22:19:40.217702

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "bfb23f323d3f"  # pragma: allowlist secret
down_revision: str | None = "436f0e73948f"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # expand only: nullable columns, so old evaluations keep meaning
    # "lens unknown" instead of claiming a lens they were never shown in
    op.add_column(
        "evaluations",
        sa.Column(
            "lens_version",
            sa.Text(),
            nullable=True,
            comment="mapeamento de exibicao usado no envio",
        ),
    )
    op.add_column(
        "evaluations",
        sa.Column(
            "exam",
            # the type already exists (initial schema); do not try to create it
            postgresql.ENUM("enem", "fuvest", name="exam", create_type=False),
            nullable=True,
            comment="lente ativa do aluno no envio",
        ),
    )


def downgrade() -> None:
    op.drop_column("evaluations", "exam")
    op.drop_column("evaluations", "lens_version")
