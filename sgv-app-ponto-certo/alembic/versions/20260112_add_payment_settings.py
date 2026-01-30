"""create payment_settings table

Revision ID: 20260112_add_payment_settings
Revises:
Create Date: 2026-01-12 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260112_add_payment_settings"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "payment_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("merchant_name", sa.String(length=100), nullable=False),
        sa.Column("chave_pix", sa.String(length=255), nullable=True),
        sa.Column("cpf_cnpj", sa.String(length=30), nullable=True),
        sa.Column("cidade", sa.String(length=50), nullable=True),
        sa.Column(
            "tipo_pix", sa.String(length=20), nullable=False, server_default="dinamico"
        ),
        sa.Column("active", sa.Boolean(), nullable=True, server_default=sa.text("1")),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table("payment_settings")
