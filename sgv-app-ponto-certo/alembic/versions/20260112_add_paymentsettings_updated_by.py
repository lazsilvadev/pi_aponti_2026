"""add paymentsettings.updated_by

Revision ID: 20260112_add_paymentsettings_updated_by
Revises: 20260112_add_payment_settings
Create Date: 2026-01-12 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260112_add_paymentsettings_updated_by"
down_revision = "20260112_add_payment_settings"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "payment_settings",
        sa.Column("updated_by", sa.String(length=100), nullable=True),
    )


def downgrade():
    op.drop_column("payment_settings", "updated_by")
