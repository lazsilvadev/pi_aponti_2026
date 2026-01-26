"""add paymentsettings.qr_image_base64

Revision ID: 20260112_add_paymentsettings_qrimage
Revises: 20260112_add_paymentsettings_updated_by
Create Date: 2026-01-12 00:00:00.000001
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260112_add_paymentsettings_qrimage"
down_revision = "20260112_add_paymentsettings_updated_by"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "payment_settings", sa.Column("qr_image_base64", sa.Text(), nullable=True)
    )


def downgrade():
    op.drop_column("payment_settings", "qr_image_base64")
