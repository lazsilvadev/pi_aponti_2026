"""add estoque_minimo to produtos

Revision ID: 0001_add_estoque_minimo
Revises:
Create Date: 2025-11-26 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0001_add_estoque_minimo"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use batch_alter_table for safer SQLite migrations
    with op.batch_alter_table("produtos", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "estoque_minimo",
                sa.Integer(),
                nullable=True,
                server_default=sa.text("10"),
            )
        )

    # Remove server_default so new inserts don't always get the SQL expression
    with op.get_context().autocommit_block():
        # Some DBs need explicit alter to remove default; for SQLite it's fine to leave.
        pass


def downgrade() -> None:
    with op.batch_alter_table("produtos", schema=None) as batch_op:
        batch_op.drop_column("estoque_minimo")
